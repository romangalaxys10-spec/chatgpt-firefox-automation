#!/usr/bin/env python3
"""
Convenience entry point - delegates to the package module.

Usage:
    python3 firefox_session.py      # extract ChatGPT cookies from Firefox
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_firefox_automation.firefox_session import extract_chatgpt_cookies

if __name__ == "__main__":
    cookies = extract_chatgpt_cookies()
    print(f"\nTotal: {len(cookies)} cookies ready for Playwright injection")