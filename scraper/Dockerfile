FROM python:3.14-slim

WORKDIR /app

# Install Chrome prerequisites and unmanaged Chrome (since SB CDP manages its own)
RUN apt-get update && apt-get install -y \
    wget gnupg2 apt-transport-https ca-certificates curl \
    xvfb \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv sync --no-dev

# Install Playwright browser binaries (Chromium only)
RUN uv run playwright install chromium

COPY . .

# Launch worker
CMD ["uv", "run", "python", "main.py"]
