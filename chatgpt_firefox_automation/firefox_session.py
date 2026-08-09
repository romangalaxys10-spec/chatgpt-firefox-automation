"""
Firefox Session Extractor for ChatGPT (chatgpt.com / auth.openai.com)
Copies the user's live Firefox profile cookies into a temp SQLite DB,
then reads the auth cookies needed for ChatGPT and formats them for Playwright.
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Dict


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


def extract_chatgpt_cookies() -> List[Dict]:
    """
    Extract ChatGPT session cookies from Firefox profile.
    Returns list of cookie dicts compatible with Playwright's context.add_cookies().
    """
    profile_db = get_firefox_profile_path()

    # Copy to temp location to avoid "database is locked" (Firefox holds a write lock)
    tmp_dir = Path(tempfile.gettempdir())
    tmp_db = tmp_dir / f"ff_chatgpt_cookies_{os.getpid()}.sqlite"
    shutil.copy2(profile_db, tmp_db)

    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # ChatGPT uses these domains:
        # - .chatgpt.com (main app)
        # - .auth.openai.com (auth flow)
        # - chatgpt.com, auth.openai.com (subdomains)
        cursor.execute("""
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            WHERE host LIKE '%chatgpt%' 
               OR host LIKE '%openai%'
            ORDER BY host
        """)
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

        print(f"[ChatGPT Firefox] Extracted {len(cookies)} cookies from Firefox profile")
        for c in cookies:
            print(f"  - {c['name']} @ {c['domain']}")
        return cookies

    finally:
        # Cleanup temp copy
        try:
            tmp_db.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    cookies = extract_chatgpt_cookies()
    print(f"\nTotal: {len(cookies)} cookies ready for Playwright injection")