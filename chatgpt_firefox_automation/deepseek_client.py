"""
DeepSeek (chat.deepseek.com) provider for the chatgpt-firefox-automation skill.

Like Qwen, chat.deepseek.com needs the full browser session to survive: it 403s
anonymous requests and uses AWS WAF (the `aws-waf-token` cookie). We reuse the
proven profile-copy approach — launch Playwright **Firefox** with
`launch_persistent_context(user_data_dir=<COPY of the real Firefox profile>)` —
so both the WAF token and the auth session carry over.

DeepSeek exposes 3 response modes via `[data-model-type="..."]` radio toggles:
  - "instant" -> model-type "default"  (DeepSeek V3, fast, non-reasoning)
  - "expert"  -> model-type "expert"   (DeepSeek R1 / DeepThink, shows reasoning)
  - "vision"  -> model-type "vision"   (image-upload capable)

The Firefox binary is resolved portably: `FIREFOX_BIN`/`FIREFOX_PROFILE` env vars
first, then the same Node Playwright cache + snap profile defaults as Qwen.
"""
import asyncio
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from playwright.async_api import BrowserContext, Page

from .qwen_client import find_firefox_binary, prepare_profile_copy
from .text_skill import TextSkill, SkillInput, SkillOutput, SkillResult
from .skill_registry import register_skill

logger = structlog.get_logger("deepseek")

COMPOSER_SEL = 'textarea[placeholder="Message DeepSeek"]'
# Model-type radio toggles: "default" (instant), "expert" (R1/DeepThink), "vision"
MODE_TO_MODEL_TYPE = {
    "instant": "default",
    "expert": "expert",
    "vision": "vision",
}
VALID_MODES = set(MODE_TO_MODEL_TYPE)

# Firefox binary + live profile — overridable via env so the controller is portable.
FIREFOX_BIN = os.environ.get("FIREFOX_BIN") or find_firefox_binary()
# Live profile dir that contains cookies.sqlite + storage/ + webappsstore.sqlite.
LIVE_PROFILE = os.environ.get("FIREFOX_PROFILE") or str(
    (Path.home() / "snap/firefox/common/.mozilla/firefox/14n5fjgr.default")
)


@dataclass
class DeepSeekMessage:
    role: str
    content: str
    mode: str = "instant"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class DeepSeekSession:
    """A single DeepSeek conversation bound to one browser page."""

    def __init__(self, session_id: str, page: Page, context: BrowserContext):
        self.session_id = session_id
        self.page = page
        self.context = context
        self.messages: List[DeepSeekMessage] = []
        self.last_activity = datetime.utcnow()

    async def send(self, prompt: str, mode: str = "instant") -> str:
        """Send a message in the given mode and return the COMPLETE response."""
        if mode not in VALID_MODES:
            mode = "instant"
        model_type = MODE_TO_MODEL_TYPE[mode]
        self.messages.append(DeepSeekMessage(role="user", content=prompt, mode=mode))
        self.last_activity = datetime.utcnow()

        # 1. Select the mode toggle (click only if not already active).
        if mode != "instant":
            toggle = self.page.locator(f'[data-model-type="{model_type}"]').first
            try:
                checked = await toggle.get_attribute("aria-checked")
                if checked != "true":
                    await toggle.click(timeout=3000)
                    await self.page.wait_for_timeout(800)
            except Exception as e:
                logger.warning("deepseek_mode_toggle", mode=mode, error=str(e)[:80])

        # 2. Type into the composer (real keystrokes, chunked for long prompts).
        await self.page.wait_for_selector(COMPOSER_SEL, timeout=15000)
        await self.page.click(COMPOSER_SEL)
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        if len(prompt) < 300:
            await self.page.keyboard.type(prompt, delay=8)
        else:
            for i in range(0, len(prompt), 120):
                await self.page.keyboard.type(prompt[i : i + 120], delay=4)
                await self.page.wait_for_timeout(40)
        await self.page.wait_for_timeout(500)

        # 3. Submit via send button, fall back to Enter.
        sent = False
        for sel in (
            'button[aria-label*="send" i]',
            'button[aria-label*="Send"]',
            ".ds-button--primary:not(.ds-button--disabled)",
        ):
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click(timeout=2000)
                    sent = True
                    break
            except Exception:
                continue
        if not sent:
            await self.page.keyboard.press("Enter")

        # 4. Wait for the streaming response to stabilize.
        response = await self._wait_for_response()
        self.messages.append(DeepSeekMessage(role="assistant", content=response, mode=mode))
        return response

    async def _wait_for_response(self, max_wait: float = 300.0) -> str:
        """Poll the last markdown block until text stops growing / stop button gone."""
        last_text = ""
        stable_since = time.time()
        saw_growth = False
        stop_sels = ['button[aria-label*="stop" i]', 'button:has-text("Stop")']

        deadline = time.time() + max_wait
        while time.time() < deadline:
            current = ""
            try:
                blocks = await self.page.query_selector_all('[class*="markdown"], .ds-markdown')
                if blocks:
                    current = (await blocks[-1].inner_text()).strip()
            except Exception:
                pass

            if len(current) > len(last_text):
                last_text = current
                stable_since = time.time()
                saw_growth = True

            stop_visible = False
            for sel in stop_sels:
                try:
                    if await self.page.locator(sel).first.is_visible(timeout=500):
                        stop_visible = True
                        break
                except Exception:
                    continue

            if not stop_visible and saw_growth:
                if time.time() - stable_since >= 5.0:
                    break
            await asyncio.sleep(0.5)

        clean = last_text.strip()
        if not clean:
            raise RuntimeError(
                "DeepSeek returned an empty response — session may be logged out "
                "or the WAF token expired. Re-authenticate at chat.deepseek.com."
            )
        return clean

    def get_history(self) -> List[Dict[str, Any]]:
        return [
            {
                "role": m.role,
                "content": m.content,
                "mode": m.mode,
                "timestamp": m.timestamp.isoformat(),
                "message_id": m.message_id,
            }
            for m in self.messages
        ]


class DeepSeekPromptInput(SkillInput):
    prompt: str
    mode: str = "instant"  # instant | expert | vision
    session_id: Optional[str] = None  # None => new chat
    headless: bool = True


class DeepSeekPromptOutput(SkillOutput):
    response: str
    session_id: str
    mode: str = "instant"
    is_new_session: bool
    message_count: int = 0


class DeepSeekHistoryInput(SkillInput):
    session_id: str


class DeepSeekHistoryOutput(SkillOutput):
    session_id: str
    messages: List[Dict[str, Any]]
    message_count: int


@register_skill
class DeepSeekSkill(TextSkill[DeepSeekPromptInput, DeepSeekPromptOutput]):
    """DeepSeek (chat.deepseek.com) automation via the user's live Firefox login.

    Uses the profile-copy + persistent-context trick (same as Qwen) so the AWS
    WAF token and session survive. Supports 3 modes: instant / expert / vision.
    """

    name: str = "deepseek"
    description: str = (
        "DeepSeek (chat.deepseek.com) automation via the user's live Firefox login "
        "(modes: instant / expert / vision)"
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._sessions: Dict[str, DeepSeekSession] = {}
        self._context: Optional[BrowserContext] = None
        self._profile_copy: Optional[Path] = None
        self._pw = None

    async def _ensure_context(self, headless: bool) -> BrowserContext:
        if self._context and not self._context.is_closed():
            return self._context

        firefox_bin = FIREFOX_BIN or find_firefox_binary()
        self._profile_copy = prepare_profile_copy()
        logger.info("deepseek_profile_copy", dir=str(self._profile_copy))

        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._context = await self._pw.firefox.launch_persistent_context(
            str(self._profile_copy),
            headless=headless,
            executable_path=firefox_bin,
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded", timeout=45000)
        # React SPA hydrate wait (early typing silently vanishes).
        await page.wait_for_timeout(6000)
        try:
            await page.wait_for_selector(COMPOSER_SEL, timeout=15000)
        except Exception:
            logger.warning("deepseek_composer_not_found")
        return self._context

    async def _get_page(self, headless: bool) -> Page:
        context = await self._ensure_context(headless)
        if context.pages:
            return context.pages[0]
        return await context.new_page()

    async def run(self, input_data: Union[DeepSeekPromptInput, SkillInput]) -> SkillResult:
        if not isinstance(input_data, DeepSeekPromptInput):
            if isinstance(input_data, dict):
                input_data = DeepSeekPromptInput(**input_data)
            else:
                return SkillResult(success=False, error=f"Unsupported input: {type(input_data)}")
        return await self.execute(input_data)

    async def execute(self, input_data: DeepSeekPromptInput) -> SkillResult:
        try:
            page = await self._get_page(input_data.headless)

            if input_data.session_id and input_data.session_id in self._sessions:
                session = self._sessions[input_data.session_id]
                is_new = False
            else:
                session_id = input_data.session_id or str(uuid.uuid4())[:12]
                session = DeepSeekSession(session_id=session_id, page=page, context=self._context)
                self._sessions[session_id] = session
                is_new = True

            response = await session.send(input_data.prompt, mode=input_data.mode)
            return SkillResult(
                success=True,
                data=DeepSeekPromptOutput(
                    response=response,
                    session_id=session.session_id,
                    mode=input_data.mode,
                    is_new_session=is_new,
                    message_count=len(session.messages),
                ),
            )
        except Exception as e:
            logger.error("deepseek_execute_error", error=str(e))
            return SkillResult(success=False, error=str(e))

    async def get_history(self, input_data: DeepSeekHistoryInput) -> SkillResult:
        session = self._sessions.get(input_data.session_id)
        if not session:
            return SkillResult(success=False, error=f"Unknown session: {input_data.session_id}")
        history = session.get_history()
        return SkillResult(
            success=True,
            data=DeepSeekHistoryOutput(
                session_id=input_data.session_id,
                messages=history,
                message_count=len(history),
            ),
        )

    async def list_sessions(self) -> List[Dict[str, Any]]:
        return [
            {
                "session_id": s.session_id,
                "message_count": len(s.messages),
                "last_activity": s.last_activity.isoformat(),
            }
            for s in self._sessions.values()
        ]

    async def shutdown(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None
        if self._profile_copy:
            try:
                shutil.rmtree(self._profile_copy, ignore_errors=True)
            except Exception:
                pass
            self._profile_copy = None
