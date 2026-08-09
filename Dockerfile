# Dockerfile for ChatGPT Firefox Automation

FROM python:3.11-slim

# Install system dependencies for Playwright and Chrome
RUN apt-get update && apt-get install -y \
    sqlite3 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN apt-get update && apt-get install -y wget gnupg \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY chatgpt_firefox_automation/ ./chatgpt_firefox_automation/
COPY firefox_session.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Install Playwright browsers
RUN playwright install chromium

# Create non-root user
RUN useradd -m -u 1000 automation && chown -R automation:automation /app
USER automation

# Default command
ENTRYPOINT ["python", "-m", "chatgpt_firefox_automation"]
CMD ["--help"]
EOF