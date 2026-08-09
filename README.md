# ChatGPT Firefox Automation

🚀 **Headless/Headful ChatGPT automation** powered by your own Firefox session — no API keys, no tokens, no account sharing. Just your logged-in ChatGPT, automated.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## ✨ What it does

| Capability | Description |
|---|---|
| 💬 **New chats** | Start fresh conversations on demand |
| 🧠 **Long conversations** | Keep one session alive across many turns — brainstorm, offload tasks, chain context |
| 📎 **File uploads** | Send JSON, text, or code files to ChatGPT and get analysis/review back |
| 🕵️ **Headless or headful** | Run invisible for automation, or visible for debugging |
| 🔐 **Zero keys needed** | Reuses your own Firefox login — cookies are extracted locally, never stored or sent |
| ⚡ **Browser pool** | Pre-warmed contexts for low-latency, concurrent sessions |
| 🔎 **History & sessions** | List conversations, inspect message history, resume any session |

## 🛠 How it works

1. **Extract** — reads your Firefox profile (`cookies.sqlite`), pulls the 30+ ChatGPT/OpenAI cookies, converts expiry from milliseconds to seconds.
2. **Drive** — launches Playwright with your system Chrome, injects cookies, and navigates to chatgpt.com.
3. **Chat** — types (real keystrokes) into the ProseMirror composer, submits via the send button, waits for the response to *finish streaming*, and returns the complete answer.
4. **Maintain** — keeps the same page/session alive for follow-up turns, so ChatGPT remembers context.

### Why it's robust
- **CSP-safe**: never uses `page.evaluate`/`wait_for_function` (blocked by ChatGPT's Content-Security-Policy) — polls DOM with Playwright locators instead.
- **Stream-aware**: waits for `button[data-testid="stop-button"]` to disappear, so you never read a partial answer and never send while the model is still busy.
- **Anti-bot**: ships a real Chrome user-agent; default Playwright UA gets Cloudflare-blocked.

## 📦 Installation

```bash
git clone https://github.com/romangalaxys10-spec/chatgpt-firefox-automation
cd chatgpt-firefox-automation
pip install -e .                # or: pip install -e .[dev]
```

**Prerequisites**
- Python 3.10+
- [Playwright](https://playwright.dev/docs/intro) + system **Google Chrome** (`/usr/bin/google-chrome-stable`)
- Firefox with an active chatgpt.com login (snap install is auto-detected)

## 🚀 Quick start

```bash
# Ask something (new chat)
python -m chatgpt_firefox_automation "What is the capital of Japan?"

# Continue the same conversation (memory preserved)
python -m chatgpt_firefox_automation --session-id <id> "What did we just discuss?"

# Upload a file and ask about it
python -m chatgpt_firefox_automation --upload data/config.json "Review this config"

# Visible browser (debugging)
python -m chatgpt_firefox_automation --headful "Tell me a joke"

# Just extract cookies
python -m chatgpt_firefox_automation --cookie-extract
```

### As a Python library

```python
import asyncio
from chatgpt_firefox_automation import ChatGPTSkill, SendPromptInput, UploadFileInput, ChatHistoryInput

async def main():
    skill = ChatGPTSkill(config={"headless": True})

    # New chat
    r1 = await skill.run(SendPromptInput(prompt="My name is Alice. Remember this."))
    print(r1.data.response, r1.data.session_id)

    # Continue the SAME chat - it remembers
    r2 = await skill.run(SendPromptInput(prompt="What is my name?", session_id=r1.data.session_id))
    print(r2.data.response)   # -> "Your name is Alice."

    # Upload a code file
    r3 = await skill.upload_file(UploadFileInput(
        file_path="src/service.py",
        prompt="Review this code for bugs",
    ))
    print(r3.response)

    # Conversation history
    hist = await skill.get_history(ChatHistoryInput(session_id=r1.data.session_id))
    for msg in hist.messages:
        print(msg["role"], msg["content"][:80])

    await skill.shutdown()

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
│   ├── browser_pool.py      # concurrent context pool
│   ├── chatgpt_client.py    # ChatGPTSkill: send / upload / history / sessions
│   └── __main__.py          # CLI
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