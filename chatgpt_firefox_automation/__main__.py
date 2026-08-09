#!/usr/bin/env python3
"""
ChatGPT Firefox Automation - CLI Entry Point

Usage:
    python -m chatgpt_firefox_automation [OPTIONS] PROMPT

Options:
    --headless / --headful    Run in headless/headful mode (default: headless)
    --session-id ID           Continue existing session
    --system-prompt TEXT      Set system prompt for new sessions
    --upload FILE             Upload a file (JSON/text/code) with the prompt
    --history                 Show conversation history
    --list-sessions           List active sessions
    --cookie-extract          Extract and print cookies only
"""
import argparse
import asyncio
import sys
from pathlib import Path

from chatgpt_firefox_automation import (
    ChatGPTSkill,
    SendPromptInput,
    ChatHistoryInput,
    UploadFileInput,
    extract_chatgpt_cookies,
)


async def main():
    parser = argparse.ArgumentParser(description="ChatGPT Firefox Automation")
    parser.add_argument("prompt", nargs="?", help="Prompt to send to ChatGPT")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless (default)")
    parser.add_argument("--headful", action="store_false", dest="headless", help="Run headful (visible browser)")
    parser.add_argument("--session-id", help="Continue existing session")
    parser.add_argument("--system-prompt", help="System prompt for new sessions")
    parser.add_argument("--upload", help="Upload a file (JSON/text/code) with the prompt")
    parser.add_argument("--history", action="store_true", help="Show conversation history")
    parser.add_argument("--list-sessions", action="store_true", help="List active sessions")
    parser.add_argument("--cookie-extract", action="store_true", help="Extract and print cookies only")

    args = parser.parse_args()

    # Handle cookie extraction
    if args.cookie_extract:
        cookies = extract_chatgpt_cookies()
        print(f"Extracted {len(cookies)} cookies:")
        for c in cookies:
            print(f"  {c['name']} @ {c['domain']}")
        return 0

    # Initialize skill
    skill = ChatGPTSkill(config={"headless": args.headless})

    try:
        if args.list_sessions:
            sessions = await skill.list_sessions()
            if sessions:
                for s in sessions:
                    print(f"  {s['session_id']}: {s['message_count']} messages, last: {s['last_activity']}")
            else:
                print("No active sessions")
            return 0

        if args.history:
            if not args.session_id:
                print("Error: --history requires --session-id")
                return 1
            result = await skill.run(ChatHistoryInput(session_id=args.session_id))
            if result.success and result.data:
                for msg in result.data.messages:
                    print(f"[{msg['role']}] {msg['content'][:100]}...")
            return 0

        # File upload mode
        if args.upload:
            upload_path = Path(args.upload)
            if not upload_path.exists():
                print(f"Error: file not found: {upload_path}", file=sys.stderr)
                return 1
            upload_input = UploadFileInput(
                file_path=str(upload_path),
                prompt=args.prompt or f"Here is the file {upload_path.name}, please review it.",
                session_id=args.session_id,
                headless=args.headless,
            )
            result = await skill.upload_file(upload_input)
            if result:
                print(f"\nSession: {result.session_id}")
                print(f"File: {result.file_name} ({result.file_size} bytes)")
                print(f"Response:\n{result.response}")
            else:
                print("Upload failed", file=sys.stderr)
                return 1
            return 0

        if not args.prompt:
            parser.print_help()
            return 1

        # Send prompt (new chat or continue session)
        result = await skill.run(SendPromptInput(
            prompt=args.prompt,
            session_id=args.session_id,
            headless=args.headless,
            system_prompt=args.system_prompt,
        ))

        if result.success:
            print(f"\nSession: {result.data.session_id} ({'new' if result.data.is_new_session else 'existing'})")
            print(f"Response:\n{result.data.response}")
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

    finally:
        await skill.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))