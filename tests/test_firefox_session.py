"""Tests for firefox_session module"""
import pytest
import sys
sys.path.insert(0, '/home/roman/.agents/skills/chatgpt-firefox-automation')

from chatgpt_firefox_automation.firefox_session import extract_chatgpt_cookies, get_firefox_profile_path


def test_get_firefox_profile_path():
    """Test that Firefox profile path is found"""
    path = get_firefox_profile_path()
    assert path.exists()
    assert path.name == "cookies.sqlite"


def test_extract_chatgpt_cookies():
    """Test cookie extraction returns valid cookies"""
    cookies = extract_chatgpt_cookies()
    assert len(cookies) > 0
    assert len(cookies) >= 30  # Should have ~32 cookies
    
    # Check required fields
    for cookie in cookies:
        assert "name" in cookie
        assert "value" in cookie
        assert "domain" in cookie
        assert "path" in cookie
        assert "secure" in cookie
        assert "httpOnly" in cookie
        assert "sameSite" in cookie
    
    # Check key cookies exist
    cookie_names = [c["name"] for c in cookies]
    assert "__Secure-next-auth.session-token.0" in cookie_names
    assert "__Secure-next-auth.session-token.1" in cookie_names
    assert "__Secure-oai-is" in cookie_names
    assert "g_state" in cookie_names


def test_cookie_expires_conversion():
    """Test that expires are converted from ms to seconds"""
    cookies = extract_chatgpt_cookies()
    for cookie in cookies:
        if "expires" in cookie:
            # Should be in seconds (reasonable timestamp)
            assert cookie["expires"] > 1000000000  # After year 2001
            assert cookie["expires"] < 2000000000  # Before year 2033
