# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD pipeline (lint, test, build, PyPI publish)

## [2.0.0] - 2026-08-11

### Added
- **DeepSeek provider** (`deepseek_client.py`) — full automation for chat.deepseek.com via profile-copy persistent context (AWS WAF token survives), with **3 response modes**:
  - `instant` → DeepSeek V3 (model-type `default`, fast, non-reasoning)
  - `expert` → DeepSeek R1 / DeepThink (model-type `expert`, shows reasoning)
  - `vision` → model-type `vision` (image-upload capable)
- `extract_deepseek_cookies()`, `deepseek` in `PROVIDER_PATTERNS` (chat.deepseek.com).
- `--provider deepseek` and `--mode instant|expert|vision` in the CLI (`__main__.py`).
- `DeepSeekSkill` registered in the skill registry + provider factory (`create_provider("deepseek")`).
- `tests/test_deepseek.py` — mode mapping, registry, cookie extraction (20 total tests, all pass).
- **Desktop Chat Studio** emerged as the `vibe-gpt-studio/` folder in this monorepo
  (Electron + React app orchestrating ChatGPT, Qwen, DeepSeek and local Ollama
  models, plus the `/brainstorm-*` skills for all three vendors).

### Changed
- Package version `1.1.1` → `2.0.0`; project description covers all three vendors.
- `skill.json` version → `2.0.0`, added `qwen_interaction` + `deepseek_interaction` capabilities.
- README/SKILL.md now document the 3-vendor usage and the monorepo layout.

### Portable
- `deepseek_client.py` resolves the Firefox binary and live profile via the
  `FIREFOX_BIN` / `FIREFOX_PROFILE` environment variables (current defaults are
  the fallback), so the controller is not tied to one machine.

## [1.1.1] - 2026-08-10

### Fixed
- **Qwen composer selector collision** (`qwen_client.py`). The composer matcher
  used a bare `'textarea.message-input-textarea, textarea, div[contenteditable="true"]'`
  selector in two places (`send()` and `_ensure_context()`). On artifact / vibe-
  coding conversations, chat.qwen.ai renders a **readonly Monaco code-editor
  textarea** (aria-label `"Editor content"`, class `inputarea monaco-mouse-cursor-
  text`) that matches the bare `textarea` clause FIRST — ahead of the real chat
  composer. The prompt was then typed into the wrong (readonly) element and the
  send button never fired, producing empty or stale responses.

  Fix: prefer the specific `textarea.message-input-textarea` selector, then fall
  back through a defensive ladder:
  1. `textarea.message-input-textarea`
  2. `div[class*="input"] textarea:not([readonly])`
  3. `div[contenteditable="true"]`

  Raises a clear `RuntimeError("Qwen composer not found…")` only if all three
  fail. Mirrors the parallel fix applied to the Node.js consumer
  (`vibe-gpt-studio/qwen_service.js`).

## [1.1.0] - 2026-08-10

### Added
- **Qwen (chat.qwen.ai) provider** — same interface as ChatGPT: new chats, long-running same-session conversations with memory, history
- `create_provider("chatgpt" | "qwen")` factory + `PROVIDERS` registry
- CLI `--provider {chatgpt,qwen}` flag
- Multi-provider cookie extraction (`extract_provider_cookies`, `extract_qwen_cookies`)
- 4 new unit tests (12 total)

### Key engineering (verified live against chat.qwen.ai)
- Qwen keeps its session token in **localStorage**; the `token` cookie is httpOnly, so cookie-only injection leaves the page logged out
- Fix: launch Playwright **Firefox** with `launch_persistent_context` on a **copy of the live Firefox profile** (cookies + storage + webappsstore + prefs) — carries cookies AND localStorage
- Reuse Node Playwright's Firefox binary (`~/.cache/ms-playwright/firefox-*/`) because Python Playwright can't install browsers on Ubuntu 26.04
- **SPA settle wait** (~6s) before typing — early typing silently vanishes
- **Count-before ordering** — read assistant message count before submitting, else fast responses race the wait
- Response selectors: `.qwen-chat-message-assistant` / `.chat-response-message`

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