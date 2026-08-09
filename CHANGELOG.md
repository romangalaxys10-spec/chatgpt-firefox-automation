# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD pipeline (lint, test, build, PyPI publish)

## [1.0.0] - 2026-08-09

### Added
- Initial release of ChatGPT Firefox Automation Skill
- **New chat sessions** - fresh conversations on demand
- **Long-running conversations** - same-session memory across turns (brainstorm, offload, chain context)
- **File uploads** - attach JSON / text / code files to the web chat for review and analysis
- **Session management** - list sessions, read message history, resume anywhere
- **Browser pool** - pre-warmed concurrent contexts
- **Headless and headful modes**
- Firefox cookie extraction with ms → seconds expiry conversion
- Playwright automation using the system Chrome binary
- NVIDIA labs-OO-Agents style architecture:
  - `TextSkill` base class with middleware pipeline (logging, timing, error handling)
  - `SkillRegistry` for skill discovery and composition
  - `RateLimitMiddleware` / `RetryMiddleware`
  - `SessionManager` with persistence and rotation
  - `BrowserPool` for concurrent sessions
- **CSP-safe DOM automation** - no `page.evaluate` / `wait_for_function` (blocked by ChatGPT CSP); locator-based polling instead
- **Stream-aware responses** - waits for `button[data-testid="stop-button"]` to clear so partial answers are never returned and messages are never sent while the model is busy
- **Anti-bot user agent** - real Chrome UA to avoid Cloudflare blocking
- CLI (`python -m chatgpt_firefox_automation`) with `--upload`, `--session-id`, `--history`, `--cookie-extract`
- Backward-compatible `chatgpt_automation.py` one-liner
- Comprehensive docs (README, CLAUDE.md, CONTRIBUTING.md, SECURITY.md)
- Unit tests (8 passing)
- Dockerfile
- Pre-commit hooks
- browser-act compatible `skill.json` manifest

### Fixed (verified live against chatgpt.com)
- Cookie expiry written in milliseconds by Firefox, now converted to seconds
- `context.add_cookies()` properly awaited
- Chat input selector: uses `div#prompt-textarea` / contenteditable (hidden fallback textarea avoided)
- Response selector: `div[data-message-author-role="assistant"]`
- Composer re-render after each message: re-query fresh nodes, type real keystrokes, click the send button (`data-testid="send-button"` / `composer-submit`), never the "Stop" state
- Load strategy: `domcontentloaded` (ChatGPT never reaches `networkidle`)

### Technical notes
- Key cookies: `__Secure-next-auth.session-token.0/1`, `__Secure-oai-is`, `oai-did`, `g_state`
- Chrome executable: `/usr/bin/google-chrome-stable`
- Firefox profile auto-detected from snap install