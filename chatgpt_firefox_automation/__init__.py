"""
ChatGPT Firefox Automation - NVIDIA labs-OO-Agents Style

TextSkill base class, SkillRegistry, and middleware for structured skill development.
"""
from .text_skill import TextSkill, SkillResult
from .skill_registry import SkillRegistry, register_skill
from .middleware import MiddlewarePipeline, LoggingMiddleware, TimingMiddleware, ErrorHandlingMiddleware
from .session_manager import SessionManager
from .browser_pool import BrowserPool
from .chatgpt_client import (
    ChatGPTSkill,
    ChatSession,
    SendPromptInput,
    SendPromptOutput,
    NewChatInput,
    NewChatOutput,
    ChatHistoryInput,
    ChatHistoryOutput,
    UploadFileInput,
    UploadFileOutput,
)
from .firefox_session import extract_chatgpt_cookies, get_firefox_profile_path

__all__ = [
    "TextSkill",
    "SkillResult", 
    "SkillRegistry",
    "register_skill",
    "MiddlewarePipeline",
    "LoggingMiddleware",
    "TimingMiddleware", 
    "ErrorHandlingMiddleware",
    "SessionManager",
    "BrowserPool",
    "ChatGPTSkill",
    "ChatSession",
    "SendPromptInput",
    "SendPromptOutput",
    "NewChatInput",
    "NewChatOutput",
    "ChatHistoryInput",
    "ChatHistoryOutput",
    "UploadFileInput",
    "UploadFileOutput",
    "extract_chatgpt_cookies",
    "get_firefox_profile_path",
]

__version__ = "1.0.0"
