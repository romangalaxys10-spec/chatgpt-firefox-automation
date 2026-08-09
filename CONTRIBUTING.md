# Contributing Guidelines

Thank you for contributing to ChatGPT Firefox Automation!

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install dependencies: `pip install -e .[dev]`
4. Install Playwright: `playwright install chromium`
5. Make your changes
6. Run tests: `pytest tests/ -v`
7. Run linting: `ruff check . && mypy chatgpt_firefox_automation`
8. Submit a pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/chatgpt-firefox-automation.git
cd chatgpt-firefox-automation

# Install in development mode
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v
```

## Code Standards

- **Python**: 3.10+ with type hints
- **Formatting**: Ruff (line length 100)
- **Type Checking**: MyPy strict mode
- **Testing**: Pytest with asyncio support
- **Logging**: Structured logging with structlog

## Pull Request Process

1. Ensure all tests pass
2. Update documentation for any API changes
3. Add tests for new functionality
4. Follow conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
5. Request review from maintainers

## Testing

- Unit tests in `tests/` - mock browser interactions
- Integration tests require Firefox profile with ChatGPT login
- CI runs on every push and PR

## Reporting Issues

- Use the bug report template
- Include Python version, OS, and error logs
- Provide minimal reproduction steps

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
EOF