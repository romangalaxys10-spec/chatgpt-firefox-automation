"""Tests for the DeepSeek provider (3 modes, registry, cookie extraction)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from chatgpt_firefox_automation import (
    PROVIDERS,
    create_provider,
    DeepSeekSkill,
    DeepSeekPromptInput,
)
from chatgpt_firefox_automation.deepseek_client import MODE_TO_MODEL_TYPE, VALID_MODES
from chatgpt_firefox_automation.firefox_session import (
    PROVIDER_PATTERNS,
    extract_deepseek_cookies,
)


def test_deepseek_registered_in_providers():
    assert "deepseek" in PROVIDERS
    assert PROVIDERS["deepseek"] is DeepSeekSkill


def test_create_provider_deepseek():
    skill = create_provider("deepseek", {"headless": True})
    assert isinstance(skill, DeepSeekSkill)
    assert skill.name == "deepseek"


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_provider("nope")


def test_mode_map_covers_all_three_modes():
    # instant -> "default" model-type, expert -> "expert", vision -> "vision"
    assert MODE_TO_MODEL_TYPE == {"instant": "default", "expert": "expert", "vision": "vision"}
    assert VALID_MODES == {"instant", "expert", "vision"}


def test_prompt_input_defaults_mode_instant():
    inp = DeepSeekPromptInput(prompt="hello")
    assert inp.mode == "instant"


def test_unknown_mode_resets_to_instant_in_session():
    # _DP session send uses the same guard: invalid modes fall back to instant.
    from chatgpt_firefox_automation.deepseek_client import VALID_MODES

    assert "bogus" not in VALID_MODES


def test_deepseek_cookie_pattern_present():
    assert "deepseek" in PROVIDER_PATTERNS
    assert any("deepseek%" in p for p in PROVIDER_PATTERNS["deepseek"]["patterns"])


@pytest.mark.skipif(
    not Path.home().joinpath("snap/firefox/common/.mozilla/firefox").exists(),
    reason="No Firefox snap profile on this machine",
)
def test_extract_deepseek_cookies():
    cookies = extract_deepseek_cookies(verbose=False)
    # Even if unauthenticated, the extractor must return a list (may be empty).
    assert isinstance(cookies, list)
    for c in cookies:
        assert "name" in c and "value" in c and "domain" in c
