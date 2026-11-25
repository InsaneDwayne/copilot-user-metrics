# One image, several entry points: `copilot-metrics api | worker | migrate | backfill | healthcheck`.
# The API also serves the built frontend, so a deployment is just this image + Postgres.
#
# The default target is the runtime image (`app`). CI also builds the `*-test` targets,
# which share the base images and dependency layers below, and runs them via ci/compose.yaml.

# --- frontend -----------------------------------------------------------------
# The built SPA is static files, so it is built once on the build host's platform, even
# for multi-arch release images (no npm under QEMU).
FROM --platform=$BUILDPLATFORM node:26-slim AS frontend-deps
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

# Lint, format check, type check and unit tests (vitest).
FROM frontend-deps AS frontend-test
CMD ["sh", "-c", "set -e; npm run lint; npx prettier --check .; npm run typecheck; npm test"]

FROM frontend-deps AS frontend
RUN npm run build

# --- backend ------------------------------------------------------------------
FROM python:3.15-slim AS backend-base
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Ruff, mypy and pytest (unit + integration). Integration tests need TEST_DATABASE_URL.
FROM backend-base AS backend-test
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-install-project
COPY backend/ ./
RUN uv sync --locked
ENV TEST_DATABASE_REQUIRED=1
CMD ["sh", "-c", "set -e; ruff check .; ruff format --check .; mypy src tests; pytest"]

# --- backend runtime ----------------------------------------------------------
FROM backend-base AS app
# Dependencies first, so source edits don't invalidate this layer.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN uv sync --locked --no-dev

# The built SPA. Only the API serves it, so API_STATIC_DIR=/app/static is set per service
# (deploy/compose.yaml), not here: an image-wide API_* variable would also land in the
# worker's environment, where a partial `api` settings group fails validation at start-up.
COPY --from=frontend /frontend/dist /app/static

# Release builds (.github/workflows/release.yml) add the full OCI label set; this one
# also lets GHCR link locally pushed images to the repository.
LABEL org.opencontainers.image.source="https://github.com/InsaneDwayne/copilot-user-metrics" \
      org.opencontainers.image.licenses="MIT"

# The release version (set by .github/workflows/release.yml; `dev` for other builds).
# Declared late so a new version only rebuilds the layers below.
ARG COPILOT_METRICS_VERSION=dev
ENV COPILOT_METRICS_VERSION=$COPILOT_METRICS_VERSION

RUN useradd --system --uid 10001 app
USER app
EXPOSE 8000
CMD ["copilot-metrics", "api", "--host", "0.0.0.0", "--port", "8000"]
