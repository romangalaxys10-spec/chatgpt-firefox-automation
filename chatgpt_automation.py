#!/usr/bin/env python3
"""
ChatGPT Firefox Automation - Backwards Compatible Entry Point

This file maintains backwards compatibility with the original simple interface.
For new projects, use the package: `from chatgpt_firefox_automation import ChatGPTSkill`
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_firefox_automation import ChatGPTSkill, SendPromptInput

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("chatgpt_automation")


async def main():
    headless = os.environ.get("CHATGPT_HEADLESS", "true").lower() == "true"
    prompt = os.environ.get("CHATGPT_PROMPT", "Tell me a joke")

    log.info(f"Launching in {'headless' if headless else 'headful'} mode")
    log.info(f"Prompt: {prompt}")

    skill = ChatGPTSkill(config={"headless": headless})
    
    try:
        result = await skill.run(SendPromptInput(prompt=prompt, headless=headless))
        
        if result.success:
            response = result.data.response
            # Save response to temp file for backwards compatibility
            resp_path = Path(tempfile.gettempdir()) / "chatgpt_response.txt"
            with open(resp_path, "w") as f:
                f.write(response)
            log.info(f"Response saved to {resp_path}")
            
            log.info(f"\n=== ChatGPT Response ===\n{response}\n=======================")
        else:
            log.error(f"Error: {result.error}")
            sys.exit(1)
    finally:
        await skill.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
