"""
ChatGPT Client - Main interface for ChatGPT interaction

Supports both:
- New chat sessions (fresh context)
- Long-running conversations (single session with history)
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator, Literal, Union

from playwright.async_api import Page
import structlog

from .browser_pool import BrowserPool, BrowserSlot
from .session_manager import SessionManager, SessionState
from .text_skill import TextSkill, SkillInput, SkillOutput, SkillResult
from .skill_registry import register_skill

logger = structlog.get_logger(__name__)


@dataclass
class ChatMessage:
    """A message in a conversation"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class ChatSession:
    """Represents a long-running ChatGPT conversation"""
    
    def __init__(
        self,
        session_id: str,
        slot: BrowserSlot,
        page: Page,
        system_prompt: Optional[str] = None
    ):
        self.session_id = session_id
        self.slot = slot
        self.page = page
        self.messages: List[ChatMessage] = []
        self.system_prompt = system_prompt
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        
        if system_prompt:
            self.messages.append(ChatMessage(role="system", content=system_prompt))
    
    async def _find_composer(self) -> str:
        """Return a fresh CSS selector for the visible prompt composer."""
        for selector in ('div#prompt-textarea', 'div[contenteditable="true"]', 'textarea'):
            if await self.page.query_selector(selector):
                return selector
        raise RuntimeError("Could not find the prompt input on ChatGPT page")
    
    async def _wait_until_idle(self, max_wait: float = 180.0) -> None:
        """Wait until ChatGPT is NOT generating (stop button gone).
        
        The definitive "busy" signal is button[data-testid="stop-button"].
        Sending while busy silently fails, so we must wait for idle first.
        """
        import time as _time
        deadline = _time.time() + max_wait
        while _time.time() < deadline:
            try:
                stops = await self.page.query_selector_all('button[data-testid="stop-button"]')
                if len(stops) == 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise TimeoutError(f"ChatGPT stayed busy for {max_wait}s")
    
    async def _submit_prompt(self, prompt: str):
        """Type into the composer and submit via the composer-submit button.
        
        - keyboard.type fires real keystrokes that ProseMirror registers.
        - The submit slot is button[class*="composer-submit"]: shows "Send" at idle,
          "Stop" while generating. We only click it when idle.
        """
        selector = await self._find_composer()
        
        # Click to focus the composer first (React re-creates nodes after each message)
        try:
            await self.page.click(selector, timeout=5000)
        except Exception:
            pass
        
        # Real keystrokes (fill does not always register in ProseMirror after re-render)
        await self.page.keyboard.type(prompt, delay=5)
        await self.page.wait_for_timeout(400)
        
        # Click the submit slot ONLY if it is NOT in "stop" state (never cancel generation).
        # ChatGPT exposes two submit variants: button[class*="composer-submit"] and
        # button[data-testid="send-button"] (the latter after file upload).
        clicked = False
        for selector in ('button[class*="composer-submit"]', 'button[data-testid="send-button"]'):
            if clicked:
                break
            btn = self.page.locator(selector)
            try:
                if await btn.count() > 0:
                    aria = await btn.first.get_attribute('aria-label') or ''
                    title = await btn.first.get_attribute('title') or ''
                    label = f"{aria} {title}".lower()
                    if "stop" not in label:
                        await btn.first.click(timeout=3000)
                        clicked = True
            except Exception:
                clicked = False
        
        if not clicked:
            await self.page.keyboard.press("Enter")

    async def send(self, prompt: str) -> str:
        """Send a message and get the complete response reliably."""
        self.messages.append(ChatMessage(role="user", content=prompt))
        self.last_activity = datetime.utcnow()
        
        # Wait for any in-flight generation to finish before typing
        await self._wait_until_idle()
        
        count_before = len(await self.page.query_selector_all('div[data-message-author-role="assistant"]'))
        
        # Submit the prompt (focus + type + submit button)
        await self._submit_prompt(prompt)
        
        # Wait for the new assistant message to appear (count must increase)
        await self._wait_for_new_assistant_message(count_before)
        
        # Wait for the response to finish streaming (stop button disappears)
        await self._wait_until_idle()
        
        # Get the latest assistant message
        elements = await self.page.query_selector_all('div[data-message-author-role="assistant"]')
        response = await elements[-1].inner_text()
        
        self.messages.append(ChatMessage(role="assistant", content=response))
        return response
    
    async def _wait_for_new_assistant_message(self, count_before: int, max_wait: float = 90.0) -> None:
        """Wait for the assistant message count to increase (CSP-safe polling)."""
        import time as _time
        deadline = _time.time() + max_wait
        while _time.time() < deadline:
            try:
                count = len(await self.page.query_selector_all('div[data-message-author-role="assistant"]'))
                if count > count_before:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise TimeoutError(f"No new assistant message after {max_wait}s")
    
    async def _wait_for_response_complete(self, stable_seconds: float = 3.0, max_wait: float = 120.0) -> None:
        """Wait until the latest assistant message text stops changing (response complete)."""
        import time as _time
        last_text = ""
        stable_since = _time.time()
        deadline = _time.time() + max_wait
        
        while _time.time() < deadline:
            try:
                elements = await self.page.query_selector_all('div[data-message-author-role="assistant"]')
                current_text = ""
                if elements:
                    current_text = (await elements[-1].inner_text()).strip()
                
                if current_text and current_text != last_text:
                    last_text = current_text
                    stable_since = _time.time()
                elif current_text and current_text == last_text:
                    if _time.time() - stable_since >= stable_seconds:
                        return
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
    async def send_streaming(self, prompt: str) -> AsyncGenerator[str, None]:
        """Send a message and stream the response (not fully implemented for ChatGPT web)"""
        # Note: ChatGPT web doesn't easily support streaming
        # This would require intercepting network responses
        response = await self.send(prompt)
        yield response
    
    async def upload_file(self, file_path: Union[str, Path], prompt: str = "Here is a file, please review it."):
        """
        Upload a file to the ChatGPT web chat and send a prompt.
        
        Args:
            file_path: Path to the file to upload (JSON, text, code, etc.)
            prompt: Optional prompt to send with the file
        
        Returns:
            str: The response from ChatGPT
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Ensure the page is loaded and the chat input is present
        try:
            await self.page.wait_for_selector('div[contenteditable="true"]', timeout=15000)
        except Exception:
            pass
        
        # ChatGPT renders file inputs lazily after hydration - wait for ANY file input
        all_inputs = self.page.locator('input[type="file"]')
        try:
            await all_inputs.first.wait_for(state="attached", timeout=15000)
        except Exception:
            pass
        
        # Pick the general file input (no accept attribute). If all have accept,
        # fall back to the first file input.
        no_accept = self.page.locator('input[type="file"]:not([accept])')
        if await no_accept.count() > 0:
            file_input = no_accept
        elif await all_inputs.count() > 0:
            file_input = all_inputs
        else:
            # Last resort: click the attach button to force the input to mount
            try:
                await self.page.click('button[aria-label*="Add files"]', timeout=5000)
                await self.page.wait_for_timeout(1500)
            except Exception:
                pass
            if await all_inputs.count() == 0:
                raise RuntimeError("Could not find file upload input on ChatGPT page")
            file_input = all_inputs
        
        # Upload the file
        await file_input.first.set_input_files(str(file_path))
        
        # Wait for the upload to COMPLETE before sending.
        # Signal: the file chip appears ready (stop/upload spinner gone) - allow up to 60s.
        await self.page.wait_for_timeout(3000)
        
        # Send the prompt after the file is attached
        if prompt:
            # Submit via the same robust path (focus + type + submit button)
            await self._submit_prompt(prompt)
            
            # Wait for NEW assistant message (count before sending) - CSP-safe polling
            count_before = len(await self.page.query_selector_all('div[data-message-author-role="assistant"]'))
            await self._wait_for_new_assistant_message(count_before)
            
            # Wait for the response to finish streaming
            await self._wait_until_idle()
            
            # Get the latest assistant message
            elements = await self.page.query_selector_all('div[data-message-author-role="assistant"]')
            response = await elements[-1].inner_text()
            
            self.messages.append(ChatMessage(role="user", content=f"[Uploaded file: {file_path.name}] {prompt}"))
            self.messages.append(ChatMessage(role="assistant", content=response))
            
            return response
        
        return "File uploaded successfully"
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "message_id": m.message_id,
            }
            for m in self.messages
        ]
    
    def clear_history(self, keep_system: bool = True):
        """Clear conversation history"""
        if keep_system and self.messages and self.messages[0].role == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []


class NewChatInput(SkillInput):
    """Input for starting a new chat"""
    headless: bool = True
    system_prompt: Optional[str] = None


class NewChatOutput(SkillOutput):
    """Output for new chat"""
    session_id: str
    message: str


class SendPromptInput(SkillInput):
    """Input for sending a prompt"""
    prompt: str
    session_id: Optional[str] = None  # If None, creates new chat
    headless: bool = True
    system_prompt: Optional[str] = None


class SendPromptOutput(SkillOutput):
    """Output for sending a prompt"""
    response: str
    session_id: str
    is_new_session: bool


class ChatHistoryInput(SkillInput):
    """Input for getting chat history"""
    session_id: str


class ChatHistoryOutput(SkillOutput):
    """Output for chat history"""
    session_id: str
    messages: List[Dict[str, Any]]
    message_count: int


class UploadFileInput(SkillInput):
    """Input for uploading a file to ChatGPT"""
    file_path: str
    prompt: str = "Here is a file, please review it."
    session_id: Optional[str] = None  # If None, creates new chat
    headless: bool = True


class UploadFileOutput(SkillOutput):
    """Output for file upload"""
    response: str
    session_id: str
    file_name: str
    file_size: int


@register_skill
class ChatGPTSkill(TextSkill[SendPromptInput, SendPromptOutput]):
    """
    Main ChatGPT Skill - Supports both new chats and long conversations.
    
    Features:
    - New chat creation
    - Session management for long conversations
    - Browser pool for concurrency
    - Session persistence
    """
    
    name = "chatgpt"
    description = "ChatGPT interaction via Firefox session cookies - supports new chats and long conversations"
    input_model = SendPromptInput
    output_model = SendPromptOutput
    timeout_seconds = 120.0
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.pool: Optional[BrowserPool] = None
        self.session_manager = SessionManager()
        self._sessions: Dict[str, ChatSession] = {}
        self._cookies: Optional[List[Dict]] = None
    
    async def _ensure_initialized(self):
        """Lazy initialization"""
        if self.pool is None:
            # Extract cookies if not already done
            if self._cookies is None:
                from .firefox_session import extract_chatgpt_cookies
                self._cookies = extract_chatgpt_cookies()
            
            self.pool = BrowserPool(
                max_size=self.config.get("pool_size", 4),
                chrome_path=self.config.get("chrome_path", "/usr/bin/google-chrome-stable"),
                headless=self.config.get("headless", True),
                cookies=self._cookies,
                config=self.config.get("browser_config", {})
            )
            await self.pool.initialize()
    
    async def execute(self, input_data: SendPromptInput) -> SendPromptOutput:
        """Execute: send prompt, maintain session if provided"""
        await self._ensure_initialized()
        
        # Get or create session
        if input_data.session_id and input_data.session_id in self._sessions:
            # Continue existing conversation
            session = self._sessions[input_data.session_id]
            self.trace("continue_session", {"session_id": input_data.session_id})
            response = await session.send(input_data.prompt)
            is_new = False
        else:
            # Create new chat session
            slot = await self.pool.acquire(session_id=input_data.session_id)
            page = slot.page
            
            # If new session_id provided but not in our sessions, use it
            session_id = input_data.session_id or str(uuid.uuid4())[:12]
            
            session = ChatSession(
                session_id=session_id,
                slot=slot,
                page=page,
                system_prompt=input_data.system_prompt
            )
            self._sessions[session_id] = session
            
            self.trace("new_session", {"session_id": session_id})
            response = await session.send(input_data.prompt)
            is_new = True
        
        return SendPromptOutput(
            response=response,
            session_id=session.session_id,
            is_new_session=is_new
        )
    
    async def new_chat(self, input_data: NewChatInput) -> NewChatOutput:
        """Start a new chat session"""
        await self._ensure_initialized()
        
        session_id = str(uuid.uuid4())[:12]
        slot = await self.pool.acquire(session_id=session_id)
        
        session = ChatSession(
            session_id=session_id,
            slot=slot,
            page=slot.page,
            system_prompt=input_data.system_prompt
        )
        self._sessions[session_id] = session
        
        return NewChatOutput(
            session_id=session_id,
            message=f"New chat session started: {session_id}"
        )
    
    async def upload_file(self, input_data: UploadFileInput) -> UploadFileOutput:
        """Upload a file to ChatGPT and get a response"""
        await self._ensure_initialized()
        
        file_path = Path(input_data.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get or create session
        if input_data.session_id and input_data.session_id in self._sessions:
            session = self._sessions[input_data.session_id]
        else:
            session_id = input_data.session_id or str(uuid.uuid4())[:12]
            slot = await self.pool.acquire(session_id=session_id)
            session = ChatSession(
                session_id=session_id,
                slot=slot,
                page=slot.page
            )
            self._sessions[session_id] = session
        
        # Upload the file and get response
        response = await session.upload_file(str(file_path), input_data.prompt)
        
        return UploadFileOutput(
            response=response,
            session_id=session.session_id,
            file_name=file_path.name,
            file_size=file_path.stat().st_size
        )
    
    async def get_history(self, input_data: ChatHistoryInput) -> ChatHistoryOutput:
        """Get conversation history for a session"""
        session = self._sessions.get(input_data.session_id)
        if not session:
            return ChatHistoryOutput(
                session_id=input_data.session_id,
                messages=[],
                message_count=0
            )
        
        return ChatHistoryOutput(
            session_id=input_data.session_id,
            messages=session.get_history(),
            message_count=len(session.messages)
        )
    
    async def close_session(self, session_id: str) -> bool:
        """Close a session and return slot to pool"""
        session = self._sessions.pop(session_id, None)
        if session:
            await self.pool.release(session.slot)
            return True
        return False
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions"""
        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_activity": s.last_activity.isoformat(),
                "message_count": len(s.messages),
            }
            for s in self._sessions.values()
        ]
    
    async def shutdown(self):
        """Shutdown all resources"""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)
        
        if self.pool:
            await self.pool.close()
            self.pool = None
