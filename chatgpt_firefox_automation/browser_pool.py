"""
Browser Pool - NVIDIA labs-OO-Agents Style

Manages a pool of browser contexts for concurrent ChatGPT sessions.
"""
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, AsyncGenerator
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BrowserSlot:
    """A slot in the browser pool"""
    context: BrowserContext
    page: Page
    in_use: bool = False
    session_id: Optional[str] = None
    created_at: float = 0.0


class BrowserPool:
    """
    Pool of browser contexts for concurrent ChatGPT sessions.
    
    Features:
    - Fixed-size pool of pre-warmed contexts
    - Automatic context recycling
    - Session affinity
    - Health checks
    """
    
    # Real Chrome user agent to avoid bot detection (Cloudflare blocks default Playwright UA)
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    )
    
    def __init__(
        self,
        max_size: int = 4,
        chrome_path: str = "/usr/bin/google-chrome-stable",
        headless: bool = True,
        cookies: Optional[List[Dict]] = None,
        config: Optional[Dict] = None
    ):
        self.max_size = max_size
        self.chrome_path = chrome_path
        self.headless = headless
        self.cookies = cookies or []
        self.config = config or {}
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._slots: List[BrowserSlot] = []
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the browser pool"""
        if self._initialized:
            return
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            executable_path=self.chrome_path,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        
        # Pre-warm slots
        for _ in range(self.max_size):
            await self._create_slot()
        
        self._initialized = True
        logger.info("browser_pool_initialized", size=self.max_size)
    
    async def _create_slot(self) -> BrowserSlot:
        """Create a new browser slot"""
        context = await self._browser.new_context(
            user_agent=self.config.get("user_agent", self.DEFAULT_USER_AGENT),
            viewport=self.config.get("viewport", {"width": 1280, "height": 720}),
        )
        
        if self.cookies:
            await context.add_cookies(self.cookies)
        
        page = await context.new_page()
        # Use domcontentloaded instead of networkidle - ChatGPT keeps connections alive
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=30000)
        # Wait for the chat interface to actually load (contenteditable means logged-in UI)
        try:
            await page.wait_for_selector('div[contenteditable="true"]', timeout=20000)
        except Exception:
            # Retry once with longer wait - Cloudflare challenge may delay render
            try:
                await page.wait_for_selector('div[contenteditable="true"]', timeout=15000)
            except Exception:
                await page.wait_for_timeout(5000)
        
        import time
        slot = BrowserSlot(
            context=context,
            page=page,
            in_use=False,
            created_at=time.time()
        )
        self._slots.append(slot)
        return slot
    
    async def acquire(self, session_id: Optional[str] = None) -> BrowserSlot:
        """Acquire a slot from the pool"""
        async with self._lock:
            # Try to find free slot
            for slot in self._slots:
                if not slot.in_use:
                    slot.in_use = True
                    slot.session_id = session_id
                    return slot
            
            # Create new slot if under max
            if len(self._slots) < self.max_size:
                slot = await self._create_slot()
                slot.in_use = True
                slot.session_id = session_id
                return slot
            
            # Wait for a slot to become free
            while True:
                for slot in self._slots:
                    if not slot.in_use:
                        slot.in_use = True
                        slot.session_id = session_id
                        return slot
                await asyncio.sleep(0.1)
    
    async def release(self, slot: BrowserSlot, keep_alive: bool = True):
        """Release a slot back to the pool"""
        async with self._lock:
            slot.in_use = False
            slot.session_id = None
            
            if not keep_alive:
                # Navigate back to home for next use
                try:
                    await slot.page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    logger.warning("slot_reset_failed", error=str(e))
                    # Recreate slot
                    await self._replace_slot(slot)
    
    async def _replace_slot(self, old_slot: BrowserSlot):
        """Replace a failed slot"""
        try:
            await old_slot.context.close()
        except:
            pass
        
        self._slots.remove(old_slot)
        await self._create_slot()
    
    async def get_for_session(self, session_id: str) -> Optional[BrowserSlot]:
        """Get slot associated with session"""
        for slot in self._slots:
            if slot.session_id == session_id and slot.in_use:
                return slot
        return None
    
    async def close(self):
        """Close all browser resources"""
        for slot in self._slots:
            try:
                await slot.context.close()
            except:
                pass
        
        if self._browser:
            await self._browser.close()
        
        if self._playwright:
            await self._playwright.stop()
        
        self._slots.clear()
        self._initialized = False
        logger.info("browser_pool_closed")
    
    def __len__(self) -> int:
        return len(self._slots)
    
    def available(self) -> int:
        return sum(1 for s in self._slots if not s.in_use)
