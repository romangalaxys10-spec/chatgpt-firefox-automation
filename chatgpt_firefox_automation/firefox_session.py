"""
Firefox Session Extractor (multi-provider)

Copies the user's live Firefox profile cookies into a temp SQLite DB,
then reads the auth cookies needed for the requested provider(s) and
formats them for Playwright.

Supported providers:
- chatgpt: chatgpt.com / auth.openai.com / openai.com
- qwen:    chat.qwen.ai / qwen.ai / qwencloud.com / alibabacloud.com / alibaba.com
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Dict, Sequence

# Provider -> SQL LIKE patterns (host) + label used in logs
PROVIDER_PATTERNS: Dict[str, Dict] = {
    "chatgpt": {
        "patterns": ["%chatgpt%", "%openai%"],
        "label": "ChatGPT",
        "site": "chatgpt.com",
    },
    "qwen": {
        "patterns": ["%qwen%", "%tongyi%", "%alibabacloud%", "%alibaba.com%", "%qwencloud%", "%passport.alibabacloud%"],
        "label": "Qwen",
        "site": "chat.qwen.ai",
    },
}


def get_firefox_profile_path() -> Path:
    """Locate the default Firefox profile cookies.sqlite under the snap install."""
    # Snap Firefox stores profile under ~/snap/firefox/common/.mozilla/firefox/
    base = Path.home() / "snap/firefox/common/.mozilla/firefox"
    if not base.exists():
        raise FileNotFoundError(f"Firefox snap profile directory not found: {base}")

    # Find the default profile (usually ends with .default or .default-release)
    profiles = list(base.glob("*.default*"))
    if not profiles:
        raise FileNotFoundError(f"No Firefox profiles found in {base}")

    # Prefer .default-release, then .default
    for pref in (".default-release", ".default"):
        for p in profiles:
            if p.name.endswith(pref):
                cookies_db = p / "cookies.sqlite"
                if cookies_db.exists():
                    return cookies_db

    # Fallback: first profile with cookies.sqlite
    for p in profiles:
        cookies_db = p / "cookies.sqlite"
        if cookies_db.exists():
            return cookies_db

    raise FileNotFoundError("No cookies.sqlite found in any Firefox profile")


def _read_cookies_for_patterns(patterns: Sequence[str]) -> List[Dict]:
    """Read + convert cookies matching any host pattern from the Firefox profile."""
    profile_db = get_firefox_profile_path()

    # Copy to temp location to avoid "database is locked" (Firefox holds a write lock)
    tmp_dir = Path(tempfile.gettempdir())
    tmp_db = tmp_dir / f"ff_cookies_{os.getpid()}.sqlite"
    shutil.copy2(profile_db, tmp_db)

    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build the WHERE clause: host LIKE p1 OR host LIKE p2 ...
        where = " OR ".join("host LIKE ?" for _ in patterns)
        cursor.execute(
            f"""
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            WHERE {where}
            ORDER BY host
            """,
            list(patterns),
        )
        rows = cursor.fetchall()
        conn.close()

        cookies = []
        for row in rows:
            # Convert Firefox sameSite (0=none, 1=lax, 2=strict) to Playwright format
            same_site_map = {0: "None", 1: "Lax", 2: "Strict"}
            same_site = same_site_map.get(row["sameSite"], "Lax")

            # Playwright expects expire as float (Unix timestamp in SECONDS), omit if session cookie
            # Firefox stores expiry in MILLISECONDS since epoch, convert to seconds
            expiry_ms = row["expiry"]
            if expiry_ms > 0:
                expires = expiry_ms / 1000.0  # Convert ms to seconds
            else:
                expires = -1  # Session cookie

            cookie = {
                "name": row["name"],
                "value": row["value"],
                "domain": row["host"].lstrip("."),  # Playwright wants domain without leading dot
                "path": row["path"],
                "secure": bool(row["isSecure"]),
                "httpOnly": bool(row["isHttpOnly"]),
                "sameSite": same_site,
            }
            if expires > 0:
                cookie["expires"] = float(expires)

            cookies.append(cookie)

        return cookies
    finally:
        # Cleanup temp copy
        try:
            tmp_db.unlink()
        except OSError:
            pass


def extract_provider_cookies(provider: str, verbose: bool = True) -> List[Dict]:
    """Extract cookies for a named provider (chatgpt | qwen)."""
    if provider not in PROVIDER_PATTERNS:
        raise ValueError(f"Unknown provider '{provider}'. Known: {list(PROVIDER_PATTERNS)}")

    cfg = PROVIDER_PATTERNS[provider]
    cookies = _read_cookies_for_patterns(cfg["patterns"])

    if verbose:
        print(f"[{cfg['label']} Firefox] Extracted {len(cookies)} cookies from Firefox profile")
        for c in cookies:
            print(f"  - {c['name']} @ {c['domain']}")

    return cookies


def extract_chatgpt_cookies(verbose: bool = True) -> List[Dict]:
    """Backwards-compatible: extract ChatGPT session cookies from Firefox profile."""
    return extract_provider_cookies("chatgpt", verbose=verbose)


def extract_qwen_cookies(verbose: bool = True) -> List[Dict]:
    """Extract Qwen (chat.qwen.ai) session cookies from Firefox profile."""
    return extract_provider_cookies("qwen", verbose=verbose)


if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "chatgpt"
    cookies = extract_provider_cookies(provider)
    print(f"\nTotal: {len(cookies)} cookies ready for Playwright injection")