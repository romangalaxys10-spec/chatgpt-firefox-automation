# ChatGPT Firefox Automation

> **v1.1.1** — fixes a Qwen composer-selector collision (bare `textarea` matched
> the readonly Monaco editor ahead of the real chat composer on artifact
> conversations). See [CHANGELOG.md](./CHANGELOG.md).

🚀 **Headless/Headful ChatGPT & Qwen automation** powered by your own Firefox session — no API keys, no tokens, no account sharing. Just your logged-in accounts, automated.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## ✨ What it does

| Capability | ChatGPT (chatgpt.com) | Qwen (chat.qwen.ai) |
|---|---|---|
| 💬 **New chats** | ✅ | ✅ |
| 🧠 **Long conversations** (one session, memory across turns) | ✅ | ✅ |
| 📎 **File uploads** (JSON/text/code) | ✅ | 🚧 |
| 🕵️ **Headless or headful** | ✅ | ✅ |
| 🔐 **Zero keys needed** | ✅ | ✅ |
| ⚡ **Browser pool / persistent context** | ✅ (pool) | ✅ (profile copy) |
| 🔎 **History & sessions** | ✅ | ✅ |

## 🛠 How it works

1. **Extract** — reads your Firefox profile (`cookies.sqlite`), pulls the session cookies, converts expiry from milliseconds to seconds.
2. **ChatGPT** — injects cookies into Playwright (system Chrome) and drives chatgpt.com.
3. **Qwen** — launches Playwright **Firefox** with `launch_persistent_context` on a **copy of your live Firefox profile** (`cookies.sqlite` + `storage/` + `webappsstore.sqlite` + `prefs.js`). This is required because chat.qwen.ai keeps its session token in **localStorage** (the `token` cookie is httpOnly, so the SPA can't read it via `document.cookie` — cookie-only injection leaves the page logged out).
4. **Chat** — types (real keystrokes), submits, waits for the response to *finish streaming*, and returns the complete answer.
5. **Maintain** — keeps the same page/session alive for follow-up turns, so the model remembers context.

### Why it's robust
- **CSP-safe**: never uses `page.evaluate`/`wait_for_function` (blocked by ChatGPT's Content-Security-Policy) — polls DOM with Playwright locators instead.
- **Stream-aware**: waits for the response to finish, so you never read a partial answer and never send while the model is still busy.
- **Anti-bot**: real browser user-agents (default Playwright UA gets Cloudflare-blocked).
- **SPA-settle**: Qwen needs a ~6s hydrate wait before typing (early typing silently vanishes).

## 📦 Installation

```bash
git clone https://github.com/romangalaxys10-spec/chatgpt-firefox-automation
cd chatgpt-firefox-automation
pip install -e .                # or: pip install -e .[dev]
```

**Prerequisites**
- Python 3.10+
- [Playwright](https://playwright.dev/docs/intro) + system **Google Chrome** (`/usr/bin/google-chrome-stable`) for ChatGPT
- Playwright **Firefox** for Qwen: `npx playwright install firefox` (Node Playwright)
- Firefox with active logins at **chatgpt.com** and **chat.qwen.ai** (snap install is auto-detected)

## 🚀 Quick start

```bash
# Ask something (new chat) - ChatGPT
python -m chatgpt_firefox_automation "What is the capital of Japan?"

# Same, but with Qwen
python -m chatgpt_firefox_automation --provider qwen "What is the capital of Japan?"

# Continue the same conversation (memory preserved)
python -m chatgpt_firefox_automation --provider qwen --session-id <id> "What did we just discuss?"

# Upload a file and ask about it (ChatGPT)
python -m chatgpt_firefox_automation --upload data/config.json "Review this config"

# Visible browser (debugging)
python -m chatgpt_firefox_automation --provider qwen --headful "Tell me a joke"

# Just extract cookies
python -m chatgpt_firefox_automation --cookie-extract
python -m chatgpt_firefox_automation --provider qwen --cookie-extract
```

### As a Python library

```python
import asyncio
from chatgpt_firefox_automation import create_provider, SendPromptInput, QwenPromptInput, UploadFileInput

async def main():
    chatgpt = create_provider("chatgpt", {"headless": True})
    qwen = create_provider("qwen", {"headless": True})

    # ChatGPT: new chat + continue
    r1 = await chatgpt.run(SendPromptInput(prompt="My name is Alice. Remember this."))
    r2 = await chatgpt.run(SendPromptInput(prompt="What is my name?", session_id=r1.data.session_id))
    print(r2.data.response)   # -> "Your name is Alice."

    # Qwen: new chat + continue (same pattern)
    q1 = await qwen.execute(QwenPromptInput(prompt="My name is Alice. Remember this."))
    q2 = await qwen.execute(QwenPromptInput(prompt="What is my name?", session_id=q1.data.session_id))
    print(q2.data.response)   # -> "Your name is Alice."

    await chatgpt.shutdown()
    await qwen.shutdown()

asyncio.run(main())
```

### Legacy one-liner

The original single-file interface is preserved:

```bash
python3 chatgpt_automation.py                          # "Tell me a joke"
CHATGPT_PROMPT="What is 2+2?" python3 chatgpt_automation.py
CHATGPT_HEADLESS=false python3 chatgpt_automation.py   # headful
```

## 🏗 Architecture

```
chatgpt-firefox-automation/
├── firefox_session.py / chatgpt_firefox_automation/firefox_session.py   # cookie extraction (ms→s expiry)
├── chatgpt_firefox_automation/
│   ├── text_skill.py        # TextSkill base + middleware pipeline (Logging/Timing/Errors)
│   ├── skill_registry.py    # SkillRegistry, @register_skill decorator
│   ├── middleware.py        # RateLimit, Retry middleware
│   ├── session_manager.py   # session persistence, rotation
│   ├── browser_pool.py      # concurrent context pool (ChatGPT)
│   ├── chatgpt_client.py    # ChatGPTSkill: send / upload / history / sessions
│   ├── qwen_client.py       # QwenSkill: profile-copy persistent context (chat.qwen.ai)
│   └── __main__.py          # CLI (--provider chatgpt|qwen)
├── tests/                   # pytest suite (8 tests)
├── skill.json               # browser-act compatible manifest
├── Dockerfile               # containerised run
└── .github/workflows/ci.yml # lint → test → build → publish
```

## 🧪 Tests

```bash
pip install -e .[dev]
pytest tests/ -v
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs are welcome!

## 🔒 Security

- Cookies are read from your local Firefox profile only — never transmitted or stored except inside the ephemeral browser session.
- No API keys. No telemetry. All traffic is direct to chatgpt.com.
- See [SECURITY.md](SECURITY.md) for full details.

## 📄 License

MIT © RyzenCode