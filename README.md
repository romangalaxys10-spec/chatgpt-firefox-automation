# ChatGPT Firefox Automation Skill

## Overview
This skill automates ChatGPT interaction via Firefox (chatgpt.com / auth.openai.com).
It extracts live Firefox session cookies, injects them into Playwright (using the installed Chrome browser), and enables headless/headful chat with ChatGPT.

## Key Concepts

### Session Cookies
ChatGPT uses these domains:
- `.chatgpt.com` - the main ChatGPT app
- `.auth.openai.com` - authentication and session management
- `.openai.com` - OpenAI API endpoints

The skill extracts all cookies for these domains from the Firefox profile and injects them into Playwright's browser context via `context.add_cookies()`.

### Modes
- **Headless**: Runs without a visible browser. Used for automation and CI.
- **Headful**: Shows the browser window. Used for manual testing and debugging.

### Environment Variables
| Variable | Purpose |
|---|---|
| `CHATGPT_HEADLESS` | Set to `false` to run in headful mode |
| `CHATGPT_PROMPT` | Default prompt text sent when starting a new chat |
| `CHATGPT_URL` | URL to navigate (default: `https://chatgpt.com`) |

## Usage

### 1. Extract cookies (run once)
```bash
python3 firefox_session.py
```
This prints all Firefox cookies for ChatGPT domains to stdout.

### 2. Start a new chat
```bash
# In headful mode:
CHATGPT_HEADLESS=false python3 chatgpt_automation.py

# In headless mode (default):
python3 chatgpt_automation.py

# Or use env vars directly:
CHATGPT_HEADLESS=false CHATGPT_PROMPT="Tell me a joke" python3 chatgpt_automation.py
```

### 3. Get the response
The response is saved to `{tempdir}/chatgpt_response.txt` for later use.

## How It Works

1. **Cookie Extraction**: Reads the Firefox profile's `cookies.sqlite` and filters for cookies on `chatgpt.com`, `auth.openai.com`, and `openai.com`. Converts Firefox's millisecond expiry timestamps to seconds for Playwright compatibility.
2. **Browser Launch**: Opens a Playwright browser using the system's installed Chrome (`/usr/bin/google-chrome-stable`), headless by default or headful when `CHATGPT_HEADLESS=false`.
3. **Cookie Injection**: Injects the extracted cookies into the browser context (using `await context.add_cookies()`).
4. **Chat Flow**:
   - Navigates to `chatgpt.com`
   - Waits for the chat interface to load
   - Fills the prompt into the contenteditable chat input div
   - Presses Enter to send
   - Waits for the assistant message to appear
   - Extracts the response from the assistant message element
   - Returns the response text

## Requirements
- Python 3.10+
- `playwright` library (`pip install playwright`)
- Playwright browsers installed (Chromium, Firefox, or Chrome) - uses system Chrome at `/usr/bin/google-chrome-stable`
- Firefox profile accessible (snap install or system install)
- The user must be logged into ChatGPT (via Firefox)

## Notes
- **This skill requires the user to be logged into ChatGPT** in Firefox.
- It uses Firefox cookies (`cookies.sqlite`) - the session cookies are automatically invalidated when the Firefox session ends.
- The skill works with the system's **snap-installed** Firefox (as typical in Ubuntu snap-based installations).
- If you use a different Firefox profile, modify `get_firefox_profile_path()` in `firefox_session.py` to point to the correct profile directory.

## License
MIT