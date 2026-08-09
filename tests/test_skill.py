"""Tests for skill components"""
import pytest
import asyncio
import sys
sys.path.insert(0, '/home/roman/.agents/skills/chatgpt-firefox-automation')

from chatgpt_firefox_automation.text_skill import (
    TextSkill, SkillInput, SkillOutput, SkillResult,
    MiddlewarePipeline, LoggingMiddleware, TimingMiddleware
)
from chatgpt_firefox_automation.skill_registry import SkillRegistry, register_skill, get_registry
from chatgpt_firefox_automation.session_manager import SessionManager, SessionState
from chatgpt_firefox_automation.middleware import RateLimitMiddleware


class SkillInputTest(SkillInput):
    value: str


class SkillOutputTest(SkillOutput):
    result: str


class SkillT(TextSkill[SkillInputTest, SkillOutputTest]):
    name = "test_skill"
    description = "Test skill"
    input_model = SkillInputTest
    output_model = SkillOutputTest
    
    async def execute(self, input_data: SkillInputTest) -> SkillOutputTest:
        return SkillOutputTest(result=f"processed: {input_data.value}")


@pytest.mark.asyncio
async def test_skill_execution():
    """Test basic skill execution"""
    skill = SkillT()
    result = await skill.run(SkillInputTest(value="hello"))
    assert result.success
    assert result.data.result == "processed: hello"
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_skill_with_middleware():
    """Test skill with custom middleware"""
    skill = SkillT()
    skill.add_middleware(LoggingMiddleware())
    skill.add_middleware(TimingMiddleware())
    
    result = await skill.run(SkillInputTest(value="test"))
    assert result.success
    assert "session_id" in result.metadata


@pytest.mark.asyncio
async def test_skill_registry():
    """Test skill registry"""
    registry = SkillRegistry()
    registry.register(SkillT)
    
    assert registry.get("test_skill") == SkillT
    assert len(registry.list_skills()) == 1
    
    skill_info = registry.list_skills()[0]
    assert skill_info["name"] == "test_skill"
    assert "input_schema" in skill_info
    assert "output_schema" in skill_info


@pytest.mark.asyncio
async def test_session_manager():
    """Test session manager"""
    manager = SessionManager()
    # Can't fully test without browser, but can test creation
    assert manager.sessions == {}
    assert manager.persistence_dir.exists()


@pytest.mark.asyncio
async def test_rate_limit_middleware():
    """Test rate limiting middleware"""
    middleware = RateLimitMiddleware(max_calls=2, window_seconds=60)
    input_data = SkillInputTest(value="test")
    
    # First two calls should work
    await middleware.before("test", input_data)
    await middleware.before("test", input_data)
    
    # Third should fail
    with pytest.raises(Exception, match="Rate limit exceeded"):
        await middleware.before("test", input_data)
