# CLAUDE.md - Instructions for AI Agents

## Project Overview
This is the ChatGPT Firefox Automation Skill - a production-ready library for headless/headful ChatGPT automation via Firefox session cookies and Playwright.

## Architecture
- **firefox_session.py**: Cookie extraction from Firefox profile with proper expires conversion
- **chatgpt_firefox_automation/**: Core package with NVIDIA labs-OO-Agents style patterns
  - **text_skill.py**: TextSkill base class with middleware pipeline
  - **skill_registry.py**: SkillRegistry for discovery and composition
  - **middleware.py**: Logging, timing, error handling, rate limiting, retry middleware
  - **session_manager.py**: Session persistence, rotation, state tracking
  - **browser_pool.py**: Concurrent browser context pool
  - **chatgpt_client.py**: Main ChatGPT skill with new chat and long conversation support

## Key Features
1. **New Chat Sessions**: Start fresh conversations with `ChatGPTSkill.execute(SendPromptInput)` without session_id
2. **Long Conversations**: Maintain context by passing session_id across calls
3. **Browser Pool**: Pre-warmed contexts for low-latency responses
4. **Session Persistence**: Save/load sessions to disk
5. **Cookie Auto-refresh**: Extract fresh cookies from Firefox on init

## Usage Patterns

### As a Skill (NVIDIA style)
```python
from chatgpt_firefox_automation import ChatGPTSkill, SendPromptInput

skill = ChatGPTSkill(config={"headless": True})
result = await skill.run(SendPromptInput(prompt="What is 2+2?"))
print(result.data.response)
```

### Long Conversation
```python
# First message - creates session
result1 = await skill.run(SendPromptInput(prompt="My name is Alice"))
session_id = result1.data.session_id

# Subsequent messages - uses same session
result2 = await skill.run(SendPromptInput(prompt="What's my name?", session_id=session_id))
```

### Direct Client Access
```python
from chatgpt_firefox_automation import ChatGPTClient

client = ChatGPTClient(headless=True)
await client.initialize()

# New chat
session = await client.new_chat()
response = await session.send("Hello")

# Get history
history = session.get_history()
```

## Development Guidelines

### Code Style
- Run `ruff check .` before commits
- Type hints required for all public APIs
- Use structlog for structured logging
- Pydantic models for all input/output

### Testing
- `pytest tests/ -v` for unit tests
- Integration tests require Firefox profile with ChatGPT login
- Mock browser for CI tests

### Adding New Skills
1. Create class inheriting from `TextSkill`
2. Define `input_model` and `output_model` as Pydantic models
3. Implement `execute` method
4. Register with `@register_skill` decorator

## Environment
- Python 3.10+
- Playwright with system Chrome (`/usr/bin/google-chrome-stable`)
- Firefox profile with active ChatGPT session

## Security
- Never commit cookies or session data
- Firefox profile path is auto-detected, not stored
- Sessions persisted locally only
- No external API keys required
EOF