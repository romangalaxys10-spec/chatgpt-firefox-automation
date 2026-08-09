# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

Please report security vulnerabilities by emailing security@ryzencode.com.

Do NOT create a public issue for security vulnerabilities.

We will respond within 48 hours and provide a fix timeline.

## Security Considerations

This library extracts Firefox session cookies for ChatGPT authentication. Important security notes:

### Cookie Handling
- Cookies are extracted from your local Firefox profile only
- No cookies are transmitted over the network (except to chatgpt.com)
- Cookies are stored in memory during execution only
- Optional session persistence writes to local disk only

### Browser Security
- Uses system-installed Chrome/Chromium (not bundled)
- Runs with sandbox disabled only when necessary (`--no-sandbox` for CI)
- No remote code execution capabilities
- No eval or dynamic code execution

### Data Privacy
- No telemetry or analytics
- No data sent to third parties
- All communication is directly with chatgpt.com
- Session data never leaves your machine

### Best Practices
1. Keep Firefox and Chrome updated
2. Use dedicated Firefox profile for automation
3. Don't share session cookies
4. Rotate sessions periodically
4. Run in isolated environments when possible

## Dependency Security

Dependencies are regularly scanned for vulnerabilities:
- `pip-audit` runs in CI
- Dependabot alerts enabled
- Minimum versions pinned in pyproject.toml
EOF