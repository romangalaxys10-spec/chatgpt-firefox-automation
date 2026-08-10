"""
ChatGPT Firefox Automation - NVIDIA labs-OO-Agents Style

Multi-provider automation (ChatGPT + Qwen) using the user's live Firefox login.
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
from .qwen_client import (
    QwenSkill,
    QwenSession,
    QwenPromptInput,
    QwenPromptOutput,
    QwenHistoryInput,
    QwenHistoryOutput,
    prepare_profile_copy,
    find_firefox_binary,
)
from .firefox_session import (
    extract_chatgpt_cookies,
    extract_qwen_cookies,
    extract_provider_cookies,
    get_firefox_profile_path,
)

# Provider registry: name -> skill class
PROVIDERS = {
    "chatgpt": ChatGPTSkill,
    "qwen": QwenSkill,
}


def create_provider(name: str, config: dict = None) -> TextSkill:
    """Factory: create a provider skill by name ('chatgpt' | 'qwen')."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Known: {list(PROVIDERS)}")
    return PROVIDERS[name](config or {})


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
    # ChatGPT
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
    # Qwen
    "QwenSkill",
    "QwenSession",
    "QwenPromptInput",
    "QwenPromptOutput",
    "QwenHistoryInput",
    "QwenHistoryOutput",
    "prepare_profile_copy",
    "find_firefox_binary",
    # Provider factory
    "PROVIDERS",
    "create_provider",
    # Cookie extraction
    "extract_chatgpt_cookies",
    "extract_qwen_cookies",
    "extract_provider_cookies",
    "get_firefox_profile_path",
]

__version__ = "1.1.0"
