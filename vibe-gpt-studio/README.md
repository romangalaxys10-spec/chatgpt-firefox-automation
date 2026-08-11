# Vibe GPT Studio — Desktop Chat Studio 🎨🤖

> **Now part of the `chatgpt-firefox-automation` monorepo.** This folder (`vibe-gpt-studio/`)
> is the desktop chat studio for ChatGPT, Qwen and DeepSeek. See the repo root
> `README.md` for the full 3-vendor picture.

**Vibe-code in a visual chat IDE** — powered by your **own web-based ChatGPT, Qwen and DeepSeek accounts** (no API keys, no billing, no limits). A desktop Electron app + browser app that talks to chatgpt.com, chat.qwen.ai and chat.deepseek.com through headless automation and streams the answers into a code-editing workspace.

---

## ✨ What it does

| Feature | Details |
|---|---|
| 🧑💻 **Visual chat IDE** | Chat with an AI while it writes code — prompts stream in, code edits land in a workspace |
| 🔀 **Three providers** | Switch between **ChatGPT** (chatgpt.com), **Qwen** (chat.qwen.ai) and **DeepSeek** (chat.deepseek.com, instant/expert/vision) — same UI, different brains |
| 🤖 **Local Ollama** | Optional local models via `ollama_service.js` (role-based planner/generator split, draft-model toggle) |
| 🔐 **Zero API keys** | Uses your live Firefox login. No tokens, no API billing, no account sharing |
| 🕵️ **Headless automation** | Playwright drives the real web UIs — no scraping, no unofficial endpoints |
| 🗂 **Session manager** | Multiple named sessions, persisted to `~/.vibe-gpt-studio/sessions/` |
| 🖥 **Electron + web** | Runs as a desktop app or in a normal browser tab |
| ⚙️ **Agentic tools** | Sub-agent orchestration, project mode (`BUILD_PROJECT`), terminal output stream |
| 🌟 **/brainstorm-* skills** | Reusable zcode skills for asking ChatGPT/Qwen/DeepSeek for a second opinion |

---

## 🏗 Architecture

```
vibe-gpt-studio/
├── server.js                  # Express + WebSocket backend (port 3099)
├── session_manager.js         # session persistence (JSON in ~/.vibe-gpt-studio/)
├── subagent_orchestrator.js   # multi-agent task decomposition
├── orchestrator.js            # project mode (plan → generate → assemble)
├── agentic_tools.js           # tool definitions for the agent
├── chatgpt_service.js         # 🔵 ChatGPT automation (cookie injection + humanized typing)
├── qwen_service.js            # 🟣 Qwen automation (profile-copy + localStorage login)
├── deepseek_service.js        # 🟠 DeepSeek automation (profile-copy, 3 modes, AWS-WAF)
├── ollama_service.js          # 🤖 local Ollama models
├── electron_main.js           # Electron shell
├── client/                    # React + Vite frontend (port 5173)
└── skills/                    # /brainstorm-{chatgpt,qwen,deepseek} zcode skills
```

### The automation strategies (hard-won, do not regress)

**ChatGPT** (`chatgpt_service.js`)
- Extracts the 30+ session cookies from the Firefox profile, injects them into Playwright.
- Types with a humanized delay, submits via the composer, waits for `div[data-message-author-role="assistant"]` to finish streaming.

**Qwen** (`qwen_service.js`)
- ⚠️ Cookie injection alone **does not work** for chat.qwen.ai — the session token lives in **localStorage** (the `token` cookie is `httpOnly`, so the SPA cannot read it via `document.cookie`).
- Fix: launch Playwright Firefox with **`launchPersistentContext` on a copy of the live Firefox profile** (`cookies.sqlite` + `storage/` + `webappsstore.sqlite` + `prefs.js`) — this carries cookies **and** localStorage, so the login survives.
- Responses are extracted from `.qwen-chat-message-assistant` with stability polling (stream-aware).

**DeepSeek** (`deepseek_service.js`)
- Same profile-copy approach (chat.deepseek.com 403s anonymous requests and uses **AWS WAF**).
- Three modes via `[data-model-type]` toggles: `instant` (V3), `expert` (R1/DeepThink), `vision`.
- Firefox binary + profile are resolved from `VIBE_FIREFOX_BIN` / `VIBE_FIREFOX_PROFILE` env (portable).

All providers share: request queueing, humanized rate limiting (5–9s jitter), session persistence, WebSocket streaming.

---

## 🚀 Run it

```bash
# 1. Install backend deps
npm install

# 2. Install + build the client (output committed to client/dist for out-of-box runs)
npm run build:client

# 3. Start the backend (needed by both web and Electron)
npm start            # http://localhost:3099

# 4a. Web app (dev)
cd client && npm run dev     # http://localhost:5173

# 4b. Desktop app
npm run electron
```

### Prerequisites
- **Firefox** with an active login at **chatgpt.com**, **chat.qwen.ai** and **chat.deepseek.com** (snap install auto-detected)
- Playwright browsers: `npx playwright install firefox`
- Node.js 18+

### Pick a provider in the UI
In the agentic chat, select **ChatGPT**, **Qwen** or **DeepSeek** (with mode) as the provider before sending. The backend dispatches to the matching controller (`server.js`).

---

## 🧪 Quick smoke tests

```bash
node -e "import('./chatgpt_service.js').then(m => new m.ChatGPTAutomationController().sendPrompt('Say OK', false).then(r => { console.log(r); process.exit(0); }))"
node -e "import('./qwen_service.js').then(m => new m.QwenAutomationController().sendPrompt('Say OK', false).then(r => { console.log(r); process.exit(0); }))"
node -e "import('./deepseek_service.js').then(m => new m.DeepSeekAutomationController().sendPrompt('Say OK', false, null, {mode:'instant'}).then(r => { console.log(r); process.exit(0); }))"
```

---

## 🔒 Security

- No API keys, no telemetry. All traffic goes directly to chatgpt.com / chat.qwen.ai / chat.deepseek.com from your machine.
- Firefox session data is read locally; the Qwen/DeepSeek profile copies live in a temp dir and are deleted on close.
- Session chat history is stored locally only (`~/.vibe-gpt-studio/sessions/`).
- See the automation core's policy in `SECURITY.md` at the repo root.

## 📄 License

MIT © RyzenCode

