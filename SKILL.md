# ChatGPT & Qwen Firefox Automation Skill

## Overview
Headless/headful automation for **ChatGPT** (chatgpt.com) and **Qwen** (chat.qwen.ai) using the user's own Firefox login. Zero API keys — the skill extracts live Firefox session state and drives the real web UIs with Playwright.

## Core Features
1. **New chat sessions** — fresh conversations on demand (`SendPromptInput` / `QwenPromptInput` without `session_id`).
2. **Long-running conversations** — pass `session_id` across calls to continue the SAME chat; the model remembers context (brainstorming, task offload, multi-turn work).
3. **File uploads** (ChatGPT) — attach JSON, text, or code files to the web chat (`UploadFileInput`).
4. **Provider switch** — `create_provider("chatgpt" | "qwen")` or CLI `--provider`.
5. **Session management** — list sessions, get message history, resume anywhere.
6. **Headless & headful** — `config={"headless": False}` shows the browser.

## Usage

### ChatGPT — new chat
```bash
python -m chatgpt_firefox_automation "Explain quantum computing"
```
```python
result = await skill.run(SendPromptInput(prompt="Explain quantum computing"))
response, session_id = result.data.response, result.data.session_id
```

### Qwen — new chat (same interface, different provider)
```bash
python -m chatgpt_firefox_automation --provider qwen "Explain quantum computing"
```
```python
result = await qwen.execute(QwenPromptInput(prompt="Explain quantum computing"))
response, session_id = result.data.response, result.data.session_id
```

### Long conversation (same session)
```bash
python -m chatgpt_firefox_automation --provider qwen --session-id <id> "And simplify that"
```
```python
r1 = await qwen.execute(QwenPromptInput(prompt="My name is Alice", session_id=sid))
r2 = await qwen.execute(QwenPromptInput(prompt="What is my name?", session_id=sid))
# r2 => "Your name is Alice."
```

### File upload (ChatGPT)
```bash
python -m chatgpt_firefox_automation --upload ./code.py "Review this code"
```
```python
r = await skill.upload_file(UploadFileInput(file_path="data.json", prompt="Summarize this data"))
```

## Critical Implementation Details (do not "fix" casually)

### ChatGPT (chatgpt.com)
- **CSP-safe DOM access**: chatgpt.com's Content-Security-Policy blocks `page.evaluate`/`wait_for_function` (unsafe-eval). Use `page.query_selector_all(...)` polling (`_wait_for_new_assistant_message`, `_wait_until_idle`).
- **Busy-composer guard**: `button[data-testid="stop-button"]` means the model is still generating. Sending while busy silently fails — always `_wait_until_idle()` before typing.
- **Real keystrokes**: `keyboard.type` (not `page.fill`) so ProseMirror registers the input after re-renders.
- **Submit slot**: click `button[data-testid="send-button"]` or `button[class*="composer-submit"]`, never when aria-label says "Stop".

### Qwen (chat.qwen.ai)
- **PROFILE-COPY IS MANDATORY**: chat.qwen.ai keeps its session token in **localStorage**; the `token` cookie is httpOnly so the SPA can't read it via `document.cookie`. Cookie-only injection → "Login or sign up" modal and messages never send.
  Launch Playwright **Firefox** with `launch_persistent_context(user_data_dir=<copy of the live profile>)`; copy `cookies.sqlite` + `storage/` + `webappsstore.sqlite` + `prefs.js`.
- **Firefox binary**: Python Playwright can't install browsers on Ubuntu 26.04 — reuse the Node Playwright install at `~/.cache/ms-playwright/firefox-*/firefox/firefox` via `executable_path`.
- **SPA settle wait**: wait ~6s after the composer appears before typing, else the text silently vanishes.
- **Count-before ordering**: read the assistant-message count BEFORE submitting (a fast response otherwise already includes the new message and the wait never fires).
- **Response selectors**: user `.chat-user-message`, assistant `.qwen-chat-message-assistant` / `.chat-response-message`; poll last element's text until stable.

### Shared
- **Cookie expiry**: Firefox's `cookies.sqlite` stores ms timestamps; Playwright needs seconds (`/1000` in `firefox_session.py`).
- **Load strategy**: `domcontentloaded` (both sites keep sockets alive forever).

## Session cookies used
- **ChatGPT**: `__Secure-next-auth.session-token.0/.1` @ chatgpt.com, `__Secure-oai-is`, `oai-did`, `g_state` @ chatgpt.com, `oai-client-auth-session/-info` @ auth.openai.com, `__cf_bm`, `__cflb` + misc.
- **Qwen**: `token` @ qwen.ai (JWT; read from localStorage by the SPA), `acw_tc` @ chat.qwen.ai (anti-bot), `aui`/`cna`/`isg`/`tfstk` @ qwen.ai, `login_qwencloud_ticket` @ qwencloud.com + misc.

## Environment
- Python 3.10+, Playwright, system Chrome at `/usr/bin/google-chrome-stable` (ChatGPT), Playwright Firefox (Qwen)
- Firefox profile auto-detected (snap: `~/snap/firefox/common/.mozilla/firefox/*.default*/cookies.sqlite`)
- User must be logged into chatgpt.com and chat.qwen.ai in Firefox

## Files
- `chatgpt_firefox_automation/chatgpt_client.py` — ChatGPTSkill (ChatGPT main entry)
- `chatgpt_firefox_automation/qwen_client.py` — QwenSkill (Qwen main entry, profile-copy)
- `chatgpt_firefox_automation/firefox_session.py` — multi-provider cookie extraction
- `chatgpt_firefox_automation/browser_pool.py` — concurrent contexts (ChatGPT)
- `chatgpt_firefox_automation/text_skill.py` — TextSkill + middleware (NVIDIA labs-OO-Agents style)
- `chatgpt_firefox_automation/__main__.py` — CLI (--provider chatgpt|qwen)
- `tests/` — pytest suite (12 tests)