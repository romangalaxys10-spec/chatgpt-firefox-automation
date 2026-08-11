# Web AI Firefox Automation — ChatGPT, Qwen & DeepSeek + Desktop Chat Studio

> **v2.0.0** — adds the **DeepSeek** provider (instant/expert/vision) and emerges
> the **Desktop Chat Studio** app as the `vibe-gpt-studio/` folder inside this repo.
> See [CHANGELOG.md](./CHANGELOG.md) and [vibe-gpt-studio/README.md](./vibe-gpt-studio/README.md).

🚀 **Headless/Headful ChatGPT, Qwen & DeepSeek automation** powered by your own Firefox session — no API keys, no tokens, no account sharing. Just your logged-in accounts, automated. Plus a full **desktop chat studio** (Electron + React) for chatting with all three vendors through a GUI.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## ✨ What it does

| Capability | ChatGPT (chatgpt.com) | Qwen (chat.qwen.ai) | DeepSeek (chat.deepseek.com) |
|---|---|---|---|
| 💬 **New chats** | ✅ | ✅ | ✅ |
| 🧠 **Long conversations** (one session, memory across turns) | ✅ | ✅ | ✅ |
| 🎛 **Response modes** | — | — | ✅ instant / expert / vision |
| 📎 **File uploads** (JSON/text/code) | ✅ | 🚧 | 🚧 |
| 🕵️ **Headless or headful** | ✅ | ✅ | ✅ |
| 🔐 **Zero keys needed** | ✅ | ✅ | ✅ |
| ⚡ **Browser pool / persistent context** | ✅ (pool) | ✅ (profile copy) | ✅ (profile copy) |
| 🔎 **History & sessions** | ✅ | ✅ | ✅ |

## 🖥 Desktop Chat Studio

This repo also contains **`vibe-gpt-studio/`** — a desktop Electron app that
orchestrates all three vendors (ChatGPT, Qwen, DeepSeek) plus local Ollama
models through a React GUI. It includes the `/brainstorm-*` skills for asking any
vendor for a second opinion.

```bash
cd vibe-gpt-studio
npm install
npm run build:client     # build the React renderer
npm start                # start the API + Electron UI (port :3099)
```

See [vibe-gpt-studio/README.md](./vibe-gpt-studio/README.md) for the full user guide.

## 🤖 Integrating with Coding Harnesses (zcode, Claude, Cursor, etc.)

This repo exposes a **local HTTP API** (`:3099`) that any coding harness — zcode, Claude, Cursor, Copilot, or a custom script — can call to offload tasks to ChatGPT, Qwen, or DeepSeek without API keys. The harness sends a prompt via JSON, the backend drives the real web UI through your logged-in Firefox session, waits for the full streaming response, and returns the complete answer over HTTP.

### The `/api/ask` endpoint

```
POST http://localhost:3099/api/ask
Content-Type: application/json
```

**Request body:**
```json
{
  "provider": "chatgpt" | "qwen" | "deepseek",
  "mode": "brainstorm" | "code" | "review" | "plan" | "debug",
  "prompt": "Your question, instruction, or task here"
}
```

**Response (success):**
```json
{
  "ok": true,
  "response": "The full answer from the AI vendor",
  "sessionId": "ask_1786433639560",
  "provider": "chatgpt",
  "mode": "brainstorm"
}
```

**Response (failure):**
```json
{
  "ok": false,
  "error": "DeepSeek composer not found — session may be logged out"
}
```

**Key rules for callers:**
1. **Always write the JSON to a temp file** and pass it with `-d @file`. Never inline the prompt in the curl command — quotes, newlines, and backticks will break the shell.
2. **Use a long timeout** (`--max-time 180`). ChatGPT takes 30–60s, Qwen 30–90s, DeepSeek expert mode up to 5 min.
3. **The backend must be running.** If you get connection refused, start it:
   ```bash
   cd ~/vibe-gpt-studio && setsid node server.js > /tmp/vibe-backend.log 2>&1 < /dev/null &
   ```
4. **Sanitize the prompt.** Strip PII / secrets before sending — the prompt goes to a third-party web service.
5. **Report honestly.** If the endpoint returns `ok: false`, surface the error. Do not fabricate a response.

### Example: zcode offloading UI design to ChatGPT + code to DeepSeek

Here is exactly how this repo was used to build the **Desktop Chat Studio** Electron app — the backend (IPC, market-data, wiring) was handled by the harness, while the UI was offloaded to ChatGPT and the code was wired together by DeepSeek.

**Step 1 — Harness writes the spec:**
The harness wrote a precise IPC contract + data shapes, then sent it to ChatGPT as a brainstorming prompt:

```bash
cat > /tmp/_ask_chatgpt.json <<'JSON'
{
  "provider": "chatgpt",
  "mode": "brainstorm",
  "prompt": "You are building a React UI for a stocks/ETF dashboard. The backend exposes these IPC methods: getQuote(symbol), getHistory(symbol, {range, interval}), getBatchQuotes(symbols[]), searchSymbols(query), getNews(symbol?). Generate a single-file App.jsx with components: Watchlist, Chart, Heatmap, News, SectorCompare. Use yahoo-finance2 data shapes. Here is the full spec: ..."
}
JSON

curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_chatgpt.json \
  --max-time 180
```

ChatGPT returned a complete React component tree with proper data-shape mapping, component hierarchy, and CSS styling — the harness extracted it via the `multifile_extractor` and wrote it into `src/renderer/`.

**Step 2 — Harness offloads code/wiring to DeepSeek:**
The harness then sent the integration wiring task to DeepSeek (expert mode for complex reasoning):

```bash
cat > /tmp/_ask_deepseek.json <<'JSON'
{
  "provider": "deepseek",
  "mode": "expert",
  "prompt": "I have a React UI that expects getHistory to return {timestamp[], open[], high[], low[], close[], volume[]} but yahoo-finance2 v4 returns {chart: [{meta: {symbol, currency}, candles: {up: [[ts, o, h, l, c, v], ...]}}]}. Write the adapter code to transform the API response into the UI contract. Also fix the chart interval mapping: 1D→5min, 1W→15min, 1M→60min, 3M→240min, 1Y→1440min. Here is the full marketData.js code: ..."
}
JSON

curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_deepseek.json \
  --max-time 180
```

DeepSeek returned the adapter function, the interval-to-period converter, and the exact lines to insert. The harness applied the edits and verified the chart rendered correctly.

**Step 3 — Harness wires it all together:**
The harness assembled the pieces: backend IPC handlers → market-data service → React UI. The result is a fully working desktop dashboard — the harness handled the integration, ChatGPT generated the UI, DeepSeek solved the data-shape mismatch. This is the pattern the harness uses repeatedly: **design offload → code reasoning → integration wiring**.

### Example: brainstorming architecture decisions across vendors

```bash
# Ask ChatGPT for approach
cat > /tmp/_ask_chatgpt.json <<'JSON'
{
  "provider": "chatgpt",
  "mode": "brainstorm",
  "prompt": "Should I use WebSocket or HTTP polling for real-time stock quotes in an Electron app? Compare latency, battery, and complexity."
}
JSON
curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_chatgpt.json --max-time 180

# Cross-check with Qwen
cat > /tmp/_ask_qwen.json <<'JSON'
{
  "provider": "qwen",
  "mode": "brainstorm",
  "prompt": "Should I use WebSocket or HTTP polling for real-time stock quotes in an Electron app? Compare latency, battery, and complexity."
}
JSON
curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_qwen.json --max-time 180

# DeepSeek expert for the final recommendation
cat > /tmp/_ask_deepseek.json <<'JSON'
{
  "provider": "deepseek",
  "mode": "expert",
  "prompt": "Given: Electron desktop app, Ubuntu, 5-second poll interval, yahoo-finance2 rate limits. WebSocket or polling? Justify with trade-offs."
}
JSON
curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_deepseek.json --max-time 180
```

### Code review / debugging

```bash
# Ask any vendor to review code
cat > /tmp/_ask_chatgpt.json <<'JSON'
{
  "provider": "chatgpt",
  "mode": "review",
  "prompt": "Review this DeepSeek controller for race conditions and memory leaks. Here is the full deepseek_client.py: ..."
}
JSON
curl -s -X POST http://localhost:3099/api/ask \
  -H 'Content-Type: application/json' \
  -d @/tmp/_ask_chatgpt.json --max-time 180
```

### Programmatic usage (Python)

```python
import requests, json

def ask_ai(provider, mode, prompt, timeout=180):
    resp = requests.post(
        "http://localhost:3099/api/ask",
        json={"provider": provider, "mode": mode, "prompt": prompt},
        timeout=timeout,
    )
    data = resp.json()
    if data["ok"]:
        return data["response"]
    raise RuntimeError(data["error"])

# ChatGPT brainstorm
answer = ask_ai("chatgpt", "brainstorm", "Is Postgres or MongoDB better for multi-tenant SaaS?")
print(answer)

# DeepSeek expert review
review = ask_ai("deepseek", "expert", "Review this Python code for thread safety: ...")
print(review)
```

### Programmatic usage (Node.js)

```javascript
const fetch = require("node-fetch");

async function askAI(provider, mode, prompt) {
  const res = await fetch("http://localhost:3099/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, mode, prompt }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error);
  return data.response;
}

// Qwen plan
const plan = await askAI("qwen", "plan", "Design a multi-file React app structure for a stock dashboard");
console.log(plan);
```

### How the harness should structure its workflow

1. **Discover** — `GET :3099/api/status` to verify the backend is alive and check cookie counts.
2. **Offload** — `POST :3099/api/ask` with the appropriate provider + mode for the task type.
3. **Parse** — check `ok: true`, use the `response` field. If `ok: false`, surface the error and optionally retry once.
4. **Iterate** — use the returned `sessionId` for follow-up turns (same session, same context).
5. **Project mode** — for multi-file tasks, use `BUILD_PROJECT` WS message or `/api/ask` with `mode: "build_project"` to get a plan, then generate all files, then assemble.
6. **Sanitize** — strip PII/secrets from prompts before sending. Report honestly when a vendor fails.

This pattern lets any coding harness or IDE agent use **three real AI vendors** through one local endpoint — no API keys, no account sharing, just your logged-in Firefox session driving the web UIs.

## 🛠 How it works

1. **Extract** — reads your Firefox profile (`cookies.sqlite`), pulls the session cookies, converts expiry from milliseconds to seconds.
2. **ChatGPT** — injects cookies into Playwright (system Chrome) and drives chatgpt.com.
3. **Qwen** — launches Playwright **Firefox** with `launch_persistent_context` on a **copy of your live Firefox profile** (`cookies.sqlite` + `storage/` + `webappsstore.sqlite` + `prefs.js`). This is required because chat.qwen.ai keeps its session token in **localStorage** (the `token` cookie is httpOnly, so the SPA can't read it via `document.cookie` — cookie-only injection leaves the page logged out).
4. **DeepSeek** — same profile-copy trick (chat.deepseek.com 403s anonymous requests and uses AWS WAF). Supports `instant` (V3), `expert` (R1) and `vision` modes via the `data-model-type` toggles.
5. **Chat** — types (real keystrokes), submits, waits for the response to *finish streaming*, and returns the complete answer.
6. **Maintain** — keeps the same page/session alive for follow-up turns, so the model remembers context.

### Why it's robust
- **CSP-safe**: never uses `page.evaluate`/`wait_for_function` (blocked by ChatGPT's Content-Security-Policy) — polls DOM with Playwright locators instead.
- **Stream-aware**: waits for the response to finish, so you never read a partial answer and never send while the model is still busy.
- **Anti-bot**: real browser user-agents (default Playwright UA gets Cloudflare-blocked).
- **SPA-settle**: Qwen & DeepSeek need a ~6s hydrate wait before typing (early typing silently vanishes).

## 📦 Installation

```bash
git clone https://github.com/romangalaxys10-spec/web-ai-firefox-automation
cd chatgpt-firefox-automation
pip install -e .                # or: pip install -e .[dev]
```

For the desktop studio, additionally:
```bash
npm install --prefix vibe-gpt-studio
npm run build:client --prefix vibe-gpt-studio
```

**Prerequisites**
- Python 3.10+
- [Playwright](https://playwright.dev/docs/intro) + system **Google Chrome** (`/usr/bin/google-chrome-stable`) for ChatGPT
- Playwright **Firefox** for Qwen & DeepSeek: `npx playwright install firefox` (Node Playwright)
- Firefox with active logins at **chatgpt.com**, **chat.qwen.ai** and **chat.deepseek.com** (snap install is auto-detected)

## 🚀 Quick start

```bash
# Ask something (new chat) - ChatGPT
python -m chatgpt_firefox_automation "What is the capital of Japan?"

# Same, but with Qwen
python -m chatgpt_firefox_automation --provider qwen "What is the capital of Japan?"

# DeepSeek — expert mode (R1 / DeepThink)
python -m chatgpt_firefox_automation --provider deepseek --mode expert "Explain black holes"

# Continue the same conversation (memory preserved)
python -m chatgpt_firefox_automation --provider qwen --session-id <id> "What did we just discuss?"

# Upload a file and ask about it (ChatGPT)
python -m chatgpt_firefox_automation --upload data/config.json "Review this config"

# Visible browser (debugging)
python -m chatgpt_firefox_automation --provider qwen --headful "Tell me a joke"

# Just extract cookies
python -m chatgpt_firefox_automation --cookie-extract
python -m chatgpt_firefox_automation --provider qwen --cookie-extract
python -m chatgpt_firefox_automation --provider deepseek --cookie-extract
```

### As a Python library

```python
import asyncio
from chatgpt_firefox_automation import create_provider, SendPromptInput, QwenPromptInput, DeepSeekPromptInput, UploadFileInput

async def main():
    chatgpt = create_provider("chatgpt", {"headless": True})
    qwen = create_provider("qwen", {"headless": True})
    deepseek = create_provider("deepseek", {"headless": True})

    # ChatGPT: new chat + continue
    r1 = await chatgpt.run(SendPromptInput(prompt="My name is Alice. Remember this."))
    r2 = await chatgpt.run(SendPromptInput(prompt="What is my name?", session_id=r1.data.session_id))
    print(r2.data.response)   # -> "Your name is Alice."

    # Qwen: new chat + continue (same pattern)
    q1 = await qwen.execute(QwenPromptInput(prompt="My name is Alice. Remember this."))
    q2 = await qwen.execute(QwenPromptInput(prompt="What is my name?", session_id=q1.data.session_id))
    print(q2.data.response)   # -> "Your name is Alice."

    # DeepSeek: pick a mode (instant | expert | vision)
    d1 = await deepseek.execute(DeepSeekPromptInput(prompt="Explain black holes", mode="expert"))
    print(d1.data.response)   # -> DeepSeek R1 reasoning answer
    print("mode:", d1.data.mode)

    await chatgpt.shutdown()
    await qwen.shutdown()
    await deepseek.shutdown()

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
├── chatgpt_firefox_automation/
│   ├── text_skill.py        # TextSkill base + middleware pipeline (Logging/Timing/Errors)
│   ├── skill_registry.py    # SkillRegistry, @register_skill decorator
│   ├── middleware.py        # RateLimit, Retry middleware
│   ├── session_manager.py   # session persistence, rotation
│   ├── browser_pool.py      # concurrent context pool (ChatGPT)
│   ├── chatgpt_client.py    # ChatGPTSkill: send / upload / history / sessions
│   ├── qwen_client.py       # QwenSkill: profile-copy persistent context (chat.qwen.ai)
│   ├── deepseek_client.py   # DeepSeekSkill: 3 modes (instant/expert/vision)
│   ├── firefox_session.py   # multi-provider cookie extraction (ms→s expiry)
│   └── __main__.py          # CLI (--provider chatgpt|qwen|deepseek, --mode)
├── tests/                   # pytest suite (20 tests)
├── vibe-gpt-studio/         # Desktop Chat Studio (Electron + React + Ollama + 3 vendors)
│   └── skills/brainstorm-{chatgpt,qwen,deepseek}/   # /brainstorm-* slash skills
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
- No API keys. No telemetry. All traffic is direct to chatgpt.com / chat.qwen.ai / chat.deepseek.com.
- See [SECURITY.md](SECURITY.md) for full details.

## 📄 License

MIT © RyzenCode