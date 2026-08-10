"""Tests for the Qwen provider (cookie extraction + profile copy helpers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from chatgpt_firefox_automation.firefox_session import extract_qwen_cookies
from chatgpt_firefox_automation.qwen_client import (
    prepare_profile_copy,
    find_firefox_binary,
)


def test_extract_qwen_cookies():
    cookies = extract_qwen_cookies(verbose=False)
    assert len(cookies) > 0
    names = {c["name"] for c in cookies}
    # Qwen's session token must be present
    assert "token" in names


def test_qwen_cookie_format():
    cookies = extract_qwen_cookies(verbose=False)
    for c in cookies:
        assert "name" in c and "value" in c and "domain" in c
        # Expiry must be seconds (or absent for session cookies)
        if "expires" in c:
            assert c["expires"] > 0


def test_find_firefox_binary():
    try:
        path = find_firefox_binary()
        assert Path(path).exists()
    except FileNotFoundError:
        pytest.skip("Playwright Firefox binary not installed on this machine")


def test_prepare_profile_copy():
    try:
        copy_dir = prepare_profile_copy()
    except FileNotFoundError:
        pytest.skip("Firefox profile not found on this machine")
    assert copy_dir.exists()
    assert (copy_dir / "cookies.sqlite").exists()
    # localStorage carry-over dirs must exist for Qwen login to survive
    assert (copy_dir / "storage").exists() or (copy_dir / "webappsstore.sqlite").exists()
    import shutil
    shutil.rmtree(copy_dir, ignore_errors=True)
