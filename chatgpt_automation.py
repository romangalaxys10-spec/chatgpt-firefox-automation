"""
ChatGPT Firefox Automation Skill - WORKING VERSION

Uses Playwright to:
1. Open a browser (headless by default, headful by flag) using installed Chrome
2. Navigate to chatgpt.com
3. Inject extracted Firefox cookies (with correct expires conversion)
4. Start a new chat, send a message, and get a response

Usage:
  python3 chatgpt_automation.py --headless    # headless mode
  python3 chatgpt_automation.py --headful      # headful mode (shows browser)
  python3 chatgpt_automation.py --url "https://chatgpt.com"
  python3 chatgpt_automation.py --prompt "Explain the solar system"

Environment variables:
  CHATGPT_HEADLESS=false  # Run in headful mode
  CHATGPT_PROMPT="..."    # Custom prompt
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright
import logging

from firefox_session import extract_chatgpt_cookies

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("chatgpt_automation")


async def send_prompt(page, prompt: str = "Tell me a joke"):
    """Send a prompt to ChatGPT and get the response."""
    log.info(f"Sending prompt: {prompt}")
    
    # Wait for the page to be ready
    await page.wait_for_timeout(3000)
    
    # Find and fill the chat input (contenteditable div is the visible one)
    try:
        await page.fill('div[contenteditable="true"]', prompt)
        log.info("Filled contenteditable div")
    except Exception as e:
        log.warning(f"Could not fill contenteditable: {e}")
        # Try alternative: click and type
        try:
            await page.click('div[contenteditable="true"]')
            await page.keyboard.type(prompt)
            log.info("Typed via keyboard")
        except Exception as e2:
            log.error(f"Failed to send prompt: {e2}")
            raise
    
    # Press Enter to send
    await page.keyboard.press("Enter")
    log.info("Sent prompt via Enter key")
    
    # Wait for response - wait for the assistant message to appear
    await page.wait_for_selector('div[data-message-author-role="assistant"]', timeout=30000)
    log.info("Assistant message appeared")
    
    # Give it a moment to fully render
    await page.wait_for_timeout(2000)
    
    # Get the response - try multiple selectors
    response = ""
    try:
        # Try the assistant message selector
        elements = await page.query_selector_all('div[data-message-author-role="assistant"]')
        if elements:
            # Get the last (most recent) assistant message
            response = await elements[-1].inner_text()
            log.info(f"Got response from assistant message: {response[:200]}...")
        else:
            # Fallback: get from aria-live
            response = await page.inner_text('div[aria-live="polite"]')
            log.info(f"Got response from aria-live: {response[:200]}...")
    except Exception as e:
        log.warning(f"Could not get response via selectors: {e}")
        # Final fallback: get page content and extract
        content = await page.content()
        # Look for assistant response in the HTML
        if "assistant" in content:
            # Extract from page
            response = content[:5000]
    
    return response


async def main():
    headless = os.environ.get("CHATGPT_HEADLESS", "true").lower() == "true"
    prompt = os.environ.get("CHATGPT_PROMPT", "Tell me a joke")

    log.info(f"Launching Playwright in {'headless' if headless else 'headful'} mode")
    log.info(f"Prompt: {prompt}")

    cookies = extract_chatgpt_cookies()

    async with async_playwright() as p:
        # Use the installed Chrome browser
        browser = await p.chromium.launch(
            headless=headless,
            executable_path="/usr/bin/google-chrome-stable",
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
        )

        # Inject Firefox cookies (with correct expires conversion)
        await context.add_cookies(cookies)
        log.info(f"Injected {len(cookies)} cookies")

        page = await context.new_page()
        await page.goto("https://chatgpt.com", wait_until="networkidle", timeout=30000)
        log.info("Opened chatgpt.com")

        # Send the prompt and get response
        response = await send_prompt(page, prompt)

        # Save response to a temp file for later use
        resp_path = Path(tempfile.gettempdir()) / "chatgpt_response.txt"
        with open(resp_path, "w") as f:
            f.write(response)
        log.info(f"Response saved to {resp_path}")

        # Log the response
        log.info(f"\n=== ChatGPT Response ===\n{response}\n=======================")

        # Close the browser
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())