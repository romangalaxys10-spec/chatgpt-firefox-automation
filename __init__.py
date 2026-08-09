#!/usr/bin/env python3
"""
ChatGPT Firefox Automation Skill

A production-ready, headless/headful ChatGPT automation library that:
- Extracts Firefox session cookies from the user's live profile
- Injects cookies into Playwright (Chrome/Firefox/Chromium)
- Enables reliable ChatGPT interaction via contenteditable input
- Supports multiple concurrent sessions and session persistence

Architecture:
- firefox_session.py: Cookie extraction with proper expires conversion
- chatgpt_client.py: High-level client for ChatGPT interaction
- browser_pool.py: Browser context pool for concurrent sessions
- session_manager.py: Session persistence and rotation

References:
- browser-act/skills: Skill structure and capabilities
- NVIDIA labs-OO-Agents: TextSkill/SkillRegistry patterns
- ix-infrastructure: Project structure, CI/CD, documentation
"""
__version__ = "1.0.0"
__author__ = "RyzenCode"
__license__ = "MIT"