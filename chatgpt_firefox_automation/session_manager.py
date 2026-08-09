"""
Session Manager - NVIDIA labs-OO-Agents Style

Manages browser sessions with persistence, rotation, and state tracking.
"""
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SessionState:
    """State of a browser session"""
    session_id: str
    created_at: datetime
    last_used: datetime
    context_id: Optional[str] = None
    page_url: Optional[str] = None
    cookies: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """
    Manages browser sessions with persistence and rotation.
    
    Features:
    - Session creation and tracking
    - Cookie persistence
    - Session rotation for long-running tasks
    - State serialization
    """
    
    def __init__(self, persistence_dir: Optional[Path] = None):
        self.sessions: Dict[str, SessionState] = {}
        self.persistence_dir = persistence_dir or Path.home() / ".chatgpt_automation" / "sessions"
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    async def create_session(
        self,
        browser: Browser,
        cookies: List[Dict],
        config: Optional[Dict] = None
    ) -> SessionState:
        """Create a new browser session with cookies"""
        async with self._lock:
            session_id = str(uuid.uuid4())
            context = await browser.new_context(
                user_agent=config.get("user_agent") if config else None,
                viewport=config.get("viewport") if config else None,
            )
            
            if cookies:
                await context.add_cookies(cookies)
            
            state = SessionState(
                session_id=session_id,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow(),
                context_id=id(context),
                cookies=cookies,
                metadata=config or {}
            )
            
            self.sessions[session_id] = state
            logger.info("session_created", session_id=session_id)
            return state
    
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    async def update_session(self, session_id: str, **updates) -> bool:
        """Update session state"""
        if session_id not in self.sessions:
            return False
        state = self.sessions[session_id]
        state.last_used = datetime.utcnow()
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return True
    
    async def close_session(self, session_id: str, context: Optional[BrowserContext] = None):
        """Close and remove session"""
        if session_id in self.sessions:
            if context:
                await context.close()
            del self.sessions[session_id]
            logger.info("session_closed", session_id=session_id)
    
    async def rotate_session(
        self,
        old_session_id: str,
        browser: Browser,
        cookies: List[Dict],
        config: Optional[Dict] = None
    ) -> SessionState:
        """Create new session and close old one"""
        old_state = self.sessions.get(old_session_id)
        new_state = await self.create_session(browser, cookies, config)
        
        if old_state:
            # Transfer any needed state
            new_state.metadata.update(old_state.metadata)
        
        return new_state
    
    async def persist_session(self, session_id: str):
        """Persist session to disk"""
        if session_id not in self.sessions:
            return
        
        state = self.sessions[session_id]
        file_path = self.persistence_dir / f"{session_id}.json"
        
        data = {
            "session_id": state.session_id,
            "created_at": state.created_at.isoformat(),
            "last_used": state.last_used.isoformat(),
            "cookies": state.cookies,
            "metadata": state.metadata,
        }
        
        file_path.write_text(json.dumps(data, indent=2))
        logger.debug("session_persisted", session_id=session_id, path=str(file_path))
    
    async def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session from disk"""
        file_path = self.persistence_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        
        data = json.loads(file_path.read_text())
        state = SessionState(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_used=datetime.fromisoformat(data["last_used"]),
            cookies=data["cookies"],
            metadata=data["metadata"],
        )
        
        self.sessions[session_id] = state
        logger.info("session_loaded", session_id=session_id)
        return state
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions"""
        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_used": s.last_used.isoformat(),
                "metadata": s.metadata,
            }
            for s in self.sessions.values()
        ]
    
    async def cleanup_old_sessions(self, max_age_hours: float = 24):
        """Remove old sessions"""
        import time
        now = datetime.utcnow()
        to_remove = [
            sid for sid, state in self.sessions.items()
            if (now - state.last_used).total_seconds() > max_age_hours * 3600
        ]
        
        for sid in to_remove:
            await self.close_session(sid)
        
        logger.info("cleanup_complete", removed=len(to_remove))
