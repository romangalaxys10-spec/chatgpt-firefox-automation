"""
Qwen (chat.qwen.ai) provider for the chatgpt-firefox-automation skill.

CRITICAL: chat.qwen.ai stores its session token in **localStorage**, and the
`token` cookie is httpOnly (invisible to the SPA via document.cookie). Cookie-only
injection therefore leaves the page logged out ("Login or sign up" modal) and
messages never send.

Solution (verified live): launch Playwright **Firefox** with
`launch_persistent_context(user_data_dir=<COPY of the real Firefox profile>)`.
Copying cookies.sqlite + storage/ + webappsstore.sqlite + prefs.js carries both
cookies AND localStorage, so the Qwen login survives.

The Python Playwright package cannot install its own browsers on Ubuntu 26.04,
so we reuse the Firefox binary installed by the Node Playwright package
(~/.cache/ms-playwright/firefox-*/firefox/firefox).
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

from .firefox_session import get_firefox_profile_path
from .text_skill import TextSkill, SkillInput, SkillOutput, SkillResult
from .skill_registry import register_skill

logger = structlog.get_logger("qwen")

# Firefox binary installed by Node Playwright (Python Playwright can't install browsers on this OS)
NODE_PLAYWRIGHT_CACHE = Path.home() / ".cache/ms-playwright"


def find_firefox_binary() -> str:
    """Locate a launchable Firefox binary (Node Playwright's install)."""
    candidates = [
        NODE_PLAYWRIGHT_CACHE / "firefox-1538" / "firefox" / "firefox",
        NODE_PLAYWRIGHT_CACHE / "firefox-1483" / "firefox" / "firefox",
        NODE_PLAYWRIGHT_CACHE / "firefox-1465" / "firefox" / "firefox",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Fallback: glob any firefox build
    matches = sorted(NODE_PLAYWRIGHT_CACHE.glob("firefox-*/firefox/firefox"))
    if matches:
        return str(matches[-1])
    raise FileNotFoundError(
        "No Playwright Firefox binary found. Run: npx playwright install firefox"
    )


def prepare_profile_copy() -> Path:
    """Copy the live Firefox profile (cookies + localStorage + prefs) to a temp dir."""
    src = get_firefox_profile_path()
    src_dir = src.parent
    copy_dir = Path(tempfile.mkdtemp(prefix="ff_profile_copy_"))
    for item in ("cookies.sqlite", "storage", "webappsstore.sqlite", "prefs.js"):
        s = src_dir / item
        if s.exists():
            if s.is_dir():
                shutil.copytree(s, copy_dir / item, dirs_exist_ok=True)
            else:
                shutil.copy2(s, copy_dir / item)
    return copy_dir


@dataclass
class QwenMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class QwenSession:
    """A single Qwen conversation bound to one browser page."""

    def __init__(self, session_id: str, page: Page, context: BrowserContext):
        self.session_id = session_id
        self.page = page
        self.context = context
        self.messages: List[QwenMessage] = []
        self.last_activity = datetime.utcnow()

    async def send(self, prompt: str) -> str:
        """Send a message and return the COMPLETE assistant response."""
        self.messages.append(QwenMessage(role="user", content=prompt))
        self.last_activity = datetime.utcnow()

        # Dismiss any welcome/login modal if it appears (should not with profile copy)
        try:
            modal = self.page.locator('button:has-text("Stay logged out")').first
            if await self.page.locator('button:has-text("Stay logged out")').count() > 0:
                await self.page.click('button:has-text("Stay logged out")', timeout=3000)
                await self.page.wait_for_timeout(1500)
        except Exception:
            pass

        # Type into the composer (real keystrokes)
        input_sel = 'textarea.message-input-textarea, textarea, div[contenteditable="true"]'
        try:
            await self.page.wait_for_selector(input_sel, timeout=15000)
        except Exception:
            raise RuntimeError("Qwen composer not found - check login state")

        # Let the SPA fully hydrate before typing (React attaches handlers lazily -
        # typing too early silently vanishes and the send button never fires)
        await self.page.wait_for_timeout(6000)

        await self.page.click(input_sel)
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        await self.page.keyboard.type(prompt, delay=12)

        # Count assistant messages BEFORE submitting - the new response is a NEW element
        assistant_sel = ".qwen-chat-message-assistant, .chat-response-message"
        count_before = len(await self.page.query_selector_all(assistant_sel))

        # Submit via send button, fall back to Enter
        sent = False
        try:
            send_btn = self.page.locator('button.send-button, button[aria-label*="send" i], button[data-testid*="send"]')
            if await send_btn.count() > 0:
                await send_btn.first.click(timeout=3000)
                sent = True
        except Exception:
            sent = False
        if not sent:
            await self.page.keyboard.press("Enter")

        # Wait for the new assistant message to appear
        await self._wait_for_count_increase(assistant_sel, count_before)

        # Wait for text to stabilize (streaming complete)
        response = await self._wait_for_stable_response(assistant_sel)

        self.messages.append(QwenMessage(role="assistant", content=response))
        return response

    async def _wait_for_count_increase(self, selector: str, count_before: int, max_wait: float = 60.0):
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                count = len(await self.page.query_selector_all(selector))
                if count > count_before:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.8)
        raise TimeoutError(f"No new Qwen assistant message after {max_wait}s")

    async def _wait_for_stable_response(self, selector: str, stable_seconds: float = 3.0, max_wait: float = 120.0) -> str:
        last_text = ""
        stable_since = time.time()
        deadline = time.time() + max_wait
        while time.time() < deadline:
            current = ""
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    current = (await elements[-1].inner_text()).strip()
            except Exception:
                pass
            if len(current) > len(last_text):
                last_text = current
                stable_since = time.time()
            elif current == last_text and len(current) > 0:
                if time.time() - stable_since >= stable_seconds:
                    return last_text
            await asyncio.sleep(0.5)
        return last_text

    def get_history(self) -> List[Dict[str, Any]]:
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "message_id": m.message_id,
            }
            for m in self.messages
        ]


class QwenPromptInput(SkillInput):
    prompt: str
    session_id: Optional[str] = None  # None => new chat
    headless: bool = True
    system_prompt: Optional[str] = None


class QwenPromptOutput(SkillOutput):
    response: str
    session_id: str
    is_new_session: bool
    message_count: int = 0


class QwenHistoryInput(SkillInput):
    session_id: str


class QwenHistoryOutput(SkillOutput):
    session_id: str
    messages: List[Dict[str, Any]]
    message_count: int


@register_skill
class QwenSkill(TextSkill[QwenPromptInput, QwenPromptOutput]):
    """Qwen (chat.qwen.ai) automation via the user's live Firefox login.

    Uses the profile-copy + persistent-context trick because Qwen keeps its
    session token in localStorage (not readable from an injected cookie).
    """

    name: str = "qwen"
    description: str = "Qwen (chat.qwen.ai) automation via the user's live Firefox login"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._sessions: Dict[str, QwenSession] = {}
        self._context: Optional[BrowserContext] = None
        self._profile_copy: Optional[Path] = None

    async def _ensure_context(self, headless: bool) -> BrowserContext:
        if self._context and not self._context.is_closed():
            return self._context

        firefox_bin = find_firefox_binary()
        self._profile_copy = prepare_profile_copy()
        logger.info("qwen_profile_copy", dir=str(self._profile_copy))

        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._context = await self._pw.firefox.launch_persistent_context(
            str(self._profile_copy),
            headless=headless,
            executable_path=firefox_bin,
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
            viewport={"width": 1280, "height": 800},
        )
        page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await page.goto("https://chat.qwen.ai", wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_selector(
                'textarea.message-input-textarea, textarea, div[contenteditable="true"]',
                timeout=20000,
            )
        except Exception:
            logger.warning("qwen_composer_not_found")
        return self._context

    async def _get_page(self, headless: bool) -> Page:
        context = await self._ensure_context(headless)
        if context.pages:
            return context.pages[0]
        return await context.new_page()

    async def run(self, input_data: Union[QwenPromptInput, SkillInput]) -> SkillResult:
        """TextSkill.run override - dispatches to Qwen session logic."""
        if not isinstance(input_data, QwenPromptInput):
            # Allow dict-style inputs
            if isinstance(input_data, dict):
                input_data = QwenPromptInput(**input_data)
            else:
                return SkillResult(success=False, error=f"Unsupported input: {type(input_data)}")
        return await self.execute(input_data)

    async def execute(self, input_data: QwenPromptInput) -> SkillResult:
        try:
            page = await self._get_page(input_data.headless)

            if input_data.session_id and input_data.session_id in self._sessions:
                session = self._sessions[input_data.session_id]
                is_new = False
            else:
                session_id = input_data.session_id or str(uuid.uuid4())[:12]
                session = QwenSession(session_id=session_id, page=page, context=self._context)
                self._sessions[session_id] = session
                is_new = True

            response = await session.send(input_data.prompt)
            return SkillResult(
                success=True,
                data=QwenPromptOutput(
                    response=response,
                    session_id=session.session_id,
                    is_new_session=is_new,
                    message_count=len(session.messages),
                ),
            )
        except Exception as e:
            logger.error("qwen_execute_error", error=str(e))
            return SkillResult(success=False, error=str(e))

    async def get_history(self, input_data: QwenHistoryInput) -> SkillResult:
        session = self._sessions.get(input_data.session_id)
        if not session:
            return SkillResult(success=False, error=f"Unknown session: {input_data.session_id}")
        history = session.get_history()
        return SkillResult(
            success=True,
            data=QwenHistoryOutput(
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
