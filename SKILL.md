# ChatGPT Firefox Automation Skill

## Overview
Headless/headful ChatGPT automation using the user's own Firefox login. Zero API keys — the skill extracts live Firefox session cookies, injects them into Playwright (system Chrome), and drives the real chatgpt.com UI.

## Core Features
1. **New chat sessions** — fresh conversations on demand (`SendPromptInput` without `session_id`).
2. **Long-running conversations** — pass `session_id` across calls to continue the SAME chat; ChatGPT remembers context (brainstorming, task offload, multi-turn work).
3. **File uploads** — attach JSON, text, or code files to the web chat and ask ChatGPT to review/analyze them (`UploadFileInput`).
4. **Session management** — list sessions, get message history, resume anywhere.
5. **Browser pool** — pre-warmed contexts for concurrency.
6. **Headless & headful** — `config={"headless": False}` shows the browser.

## Usage

### New chat
```bash
python -m chatgpt_firefox_automation "Explain quantum computing"
```
```python
result = await skill.run(SendPromptInput(prompt="Explain quantum computing"))
response, session_id = result.data.response, result.data.session_id
```

### Long conversation (same session)
```bash
python -m chatgpt_firefox_automation --session-id <id> "And simplify that"
```
```python
r1 = await skill.run(SendPromptInput(prompt="My name is Alice", session_id=sid))
r2 = await skill.run(SendPromptInput(prompt="What is my name?", session_id=sid))
# r2 => "Your name is Alice."
```

### File upload
```bash
python -m chatgpt_firefox_automation --upload ./code.py "Review this code"
```
```python
r = await skill.upload_file(UploadFileInput(file_path="data.json", prompt="Summarize this data"))
```

### History
```python
hist = await skill.get_history(ChatHistoryInput(session_id=sid))
```

## Critical Implementation Details (do not "fix" casually)
- **CSP-safe DOM access**: chatgpt.com's Content-Security-Policy blocks `page.evaluate`/`wait_for_function` (unsafe-eval). Use `page.query_selector_all(...)` polling (`_wait_for_new_assistant_message`, `_wait_until_idle`).
- **Busy-composer guard**: `button[data-testid="stop-button"]` means the model is still generating. Sending while busy silently fails — always `_wait_until_idle()` before typing.
- **Real keystrokes**: `keyboard.type` (not `page.fill`) so ProseMirror registers the input after re-renders.
- **Submit slot**: click `button[data-testid="send-button"]` or `button[class*="composer-submit"]`, never when aria-label says "Stop".
- **User-agent**: must be a real Chrome UA (`BrowserPool.DEFAULT_USER_AGENT`) or Cloudflare blocks the page (contenteditable never mounts).
- **Cookie expiry**: Firefox's `cookies.sqlite` stores ms timestamps; Playwright needs seconds (`/1000` in `firefox_session.py`).
- **Load strategy**: `domcontentloaded` (not `networkidle` — ChatGPT keeps sockets alive forever).

## Session cookies used
- `__Secure-next-auth.session-token.0/.1` @ chatgpt.com (login)
- `__Secure-oai-is`, `oai-did`, `g_state`, `oai-sc`, `oai-hlib` @ chatgpt.com
- `oai-client-auth-session/-info`, `unified_session_manifest` @ auth.openai.com
- `__cf_bm`, `__cflb` (Cloudflare) + misc

## Environment
- Python 3.10+, Playwright, system Chrome at `/usr/bin/google-chrome-stable`
- Firefox profile auto-detected (snap: `~/snap/firefox/common/.mozilla/firefox/*.default*/cookies.sqlite`)
- User must be logged into chatgpt.com in Firefox

## Files
- `chatgpt_firefox_automation/chatgpt_client.py` — ChatGPTSkill (main entry)
- `chatgpt_firefox_automation/browser_pool.py` — concurrent contexts
- `chatgpt_firefox_automation/text_skill.py` — TextSkill + middleware (NVIDIA labs-OO-Agents style)
- `chatgpt_firefox_automation/skill_registry.py` — SkillRegistry
- `chatgpt_firefox_automation/session_manager.py` — persistence/rotation
- `chatgpt_firefox_automation/firefox_session.py` — cookie extraction
- `chatgpt_firefox_automation/__main__.py` — CLI
- `tests/` — pytest suite