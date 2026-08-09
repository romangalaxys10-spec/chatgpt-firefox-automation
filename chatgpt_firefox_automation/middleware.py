"""
Middleware Pipeline - NVIDIA labs-OO-Agents Style

Advanced middleware for skill execution pipeline.
"""
from .text_skill import (
    Middleware,
    MiddlewarePipeline,
    SkillResult,
    SkillInput,
    LoggingMiddleware,
    TimingMiddleware,
    ErrorHandlingMiddleware,
)

# Re-export
__all__ = [
    "Middleware",
    "MiddlewarePipeline",
    "SkillResult",
    "SkillInput",
    "LoggingMiddleware",
    "TimingMiddleware",
    "ErrorHandlingMiddleware",
    "RateLimitMiddleware",
    "RetryMiddleware",
]

# Additional middleware classes


class RateLimitMiddleware(Middleware):
    """Rate limiting middleware"""
    
    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: Dict[str, List[float]] = {}
    
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        import time
        now = time.time()
        if skill_name not in self.calls:
            self.calls[skill_name] = []
        
        # Clean old calls
        self.calls[skill_name] = [t for t in self.calls[skill_name] if now - t < self.window_seconds]
        
        if len(self.calls[skill_name]) >= self.max_calls:
            raise Exception(f"Rate limit exceeded for {skill_name}")
        
        self.calls[skill_name].append(now)
        return input_data
    
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        return result
    
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        return SkillResult(success=False, error=str(error))


class RetryMiddleware(Middleware):
    """Retry middleware with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        return input_data
    
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        return result
    
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        # This middleware handles retries at a higher level
        return SkillResult(success=False, error=str(error))
