"""
TextSkill Base Class - NVIDIA labs-OO-Agents Style

Provides a structured base for text-based skills with:
- Structured input/output schemas
- Middleware pipeline support
- Session/state management
- Trace/capture capabilities
- Async execution with timeout handling
"""
import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


@dataclass
class SkillResult(Generic[T]):
    """Result of a skill execution"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    trace: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data.model_dump() if self.data else None,
            "error": self.error,
            "trace": self.trace,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class SkillInput(BaseModel):
    """Base input schema for skills"""
    model_config = ConfigDict(extra="forbid")


class SkillOutput(BaseModel):
    """Base output schema for skills"""
    model_config = ConfigDict(extra="forbid")


class Middleware(ABC):
    """Middleware interface for skill pipeline"""
    
    @abstractmethod
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        """Process before skill execution"""
        pass
    
    @abstractmethod
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        """Process after skill execution"""
        pass
    
    @abstractmethod
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        """Handle errors"""
        pass


class LoggingMiddleware(Middleware):
    """Logs skill execution"""
    
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        logger.info("skill_started", skill=skill_name, input=input_data.model_dump())
        return input_data
    
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        logger.info("skill_completed", skill=skill_name, success=result.success, duration_ms=result.duration_ms)
        return result
    
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        logger.error("skill_failed", skill=skill_name, error=str(error))
        return SkillResult(success=False, error=str(error))


class TimingMiddleware(Middleware):
    """Measures skill execution time"""
    
    def __init__(self):
        self._start_times: Dict[str, float] = {}
    
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        self._start_times[skill_name] = time.perf_counter()
        return input_data
    
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        if skill_name in self._start_times:
            result.duration_ms = (time.perf_counter() - self._start_times[skill_name]) * 1000
        return result
    
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        duration = 0
        if skill_name in self._start_times:
            duration = (time.perf_counter() - self._start_times[skill_name]) * 1000
        return SkillResult(success=False, error=str(error), duration_ms=duration)


class ErrorHandlingMiddleware(Middleware):
    """Handles errors gracefully"""
    
    async def before(self, skill_name: str, input_data: SkillInput) -> Optional[SkillInput]:
        return input_data
    
    async def after(self, skill_name: str, result: SkillResult) -> SkillResult:
        return result
    
    async def on_error(self, skill_name: str, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            error=f"{type(error).__name__}: {error}",
            metadata={"error_type": type(error).__name__}
        )


class MiddlewarePipeline:
    """Pipeline for executing middleware"""
    
    def __init__(self):
        self.middlewares: List[Middleware] = []
    
    def add(self, middleware: Middleware) -> "MiddlewarePipeline":
        self.middlewares.append(middleware)
        return self
    
    async def execute_before(self, skill_name: str, input_data: SkillInput) -> SkillInput:
        for mw in self.middlewares:
            result = await mw.before(skill_name, input_data)
            if result is not None:
                input_data = result
        return input_data
    
    async def execute_after(self, skill_name: str, result: SkillResult) -> SkillResult:
        for mw in reversed(self.middlewares):
            result = await mw.after(skill_name, result)
        return result
    
    async def execute_error(self, skill_name: str, error: Exception) -> SkillResult:
        result = SkillResult(success=False, error=str(error))
        for mw in self.middlewares:
            result = await mw.on_error(skill_name, error)
        return result


class TextSkill(ABC, Generic[T, U]):
    """
    Base class for text-based skills - NVIDIA labs-OO-Agents style.
    
    Provides:
    - Structured input/output via Pydantic models
    - Middleware pipeline
    - Session management
    - Trace capturing
    - Timeout handling
    """
    
    name: str = "unnamed_skill"
    description: str = ""
    input_model: type[T] = SkillInput
    output_model: type[U] = SkillOutput
    timeout_seconds: float = 30.0
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.pipeline = MiddlewarePipeline()
        self.pipeline.add(LoggingMiddleware())
        self.pipeline.add(TimingMiddleware())
        self.pipeline.add(ErrorHandlingMiddleware())
        self._session_id = str(uuid.uuid4())
        self._traces: List[Dict[str, Any]] = []
    
    def add_middleware(self, middleware: Middleware) -> "TextSkill":
        self.pipeline.add(middleware)
        return self
    
    @abstractmethod
    async def execute(self, input_data: T) -> U:
        """Execute the skill logic"""
        pass
    
    async def run(self, input_data: T) -> SkillResult[U]:
        """Run skill with full pipeline"""
        start_time = time.perf_counter()
        
        # Before middleware
        processed_input = await self.pipeline.execute_before(self.name, input_data)
        if not isinstance(processed_input, self.input_model):
            processed_input = self.input_model.model_validate(processed_input.model_dump())
        
        try:
            # Execute skill
            output = await asyncio.wait_for(
                self.execute(processed_input),
                timeout=self.timeout_seconds
            )
            
            result = SkillResult(
                success=True,
                data=output,
                duration_ms=(time.perf_counter() - start_time) * 1000,
                trace=self._traces,
                metadata={"session_id": self._session_id}
            )
            
        except asyncio.TimeoutError:
            result = SkillResult(
                success=False,
                error=f"Timeout after {self.timeout_seconds}s",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                trace=self._traces
            )
        except Exception as e:
            result = await self.pipeline.execute_error(self.name, e)
            result.duration_ms = (time.perf_counter() - start_time) * 1000
            result.trace = self._traces
        
        # After middleware
        return await self.pipeline.execute_after(self.name, result)
    
    def trace(self, event: str, data: Dict[str, Any]):
        """Add trace event"""
        self._traces.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data,
        })
    
    @asynccontextmanager
    async def session(self):
        """Context manager for skill session"""
        self.trace("session_start", {"session_id": self._session_id})
        try:
            yield self
        finally:
            self.trace("session_end", {"session_id": self._session_id})
