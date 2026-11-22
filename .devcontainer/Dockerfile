# Playwright's Chromium for the documentation screenshots (tools/screenshots/), taken from
# Microsoft's Playwright image for Python, without downloading it from Playwright's host (blocked
# on some networks). The Python image, not the Node.js one (mcr.microsoft.com/playwright): the
# two packages share version numbers but not always the Chromium build. Keep the tag at the
# `playwright` version in backend/uv.lock; Dependabot proposes both updates. Only Chromium is kept.
FROM mcr.microsoft.com/playwright/python:v1.65.1-noble AS playwright
RUN rm -rf /ms-playwright/firefox-* /ms-playwright/webkit-*

FROM mcr.microsoft.com/devcontainers/typescript-node:26-trixie

# psql for poking at the database; libpq for psycopg; Chromium's system libraries and the fonts
# Playwright installs with --with-deps, as in the Screenshots workflow (Playwright's Debian 13
# list for chromium, without xvfb: the screenshots run headless).
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        postgresql-client \
        libpq-dev \
        libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libcairo2 \
        libcups2t64 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 libnspr4 libnss3 \
        libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
        libxkbcommon0 libxrandr2 \
        libfontconfig1 libfreetype6 fonts-liberation fonts-noto-color-emoji fonts-unifont \
        xfonts-scalable fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
        fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Playwright (a locked dependency of the backend's `screenshots` group, installed by
# `just install`) finds its browsers here.
COPY --from=playwright /ms-playwright /ms-playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# uv manages Python itself plus the backend's dependencies and virtualenv.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /usr/local/bin/

ENV PYTHON_VERSION=3.14 \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PYTHON_BIN_DIR=/usr/local/bin \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install a uv-managed CPython system-wide and expose it as python / python3.
RUN uv python install "${PYTHON_VERSION}" --default \
    && chmod -R a+rX /opt/uv \
    && python --version

# just runs the project's task recipes (see /workspace/justfile).
ARG JUST_VERSION=1.59.0
RUN arch="$(uname -m)" \
    && curl -fsSL "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-${arch}-unknown-linux-musl.tar.gz" \
        | tar -xz -C /usr/local/bin just \
    && just --version

# pre-commit runs the git hooks in /workspace/.pre-commit-config.yaml; installed as a uv tool.
ARG PRE_COMMIT_VERSION=4.7.0
ENV UV_TOOL_DIR=/opt/uv/tools \
    UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "pre-commit==${PRE_COMMIT_VERSION}" \
    && chmod -R a+rX /opt/uv/tools \
    && pre-commit --version
