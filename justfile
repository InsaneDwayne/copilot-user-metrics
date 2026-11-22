# Project tasks. Run `just` to list them.

set shell := ["bash", "-euo", "pipefail", "-c"]

backend := "uv run --directory backend"

# List the recipes
default:
    @just --list --unsorted

# Install backend and frontend dependencies and the git hook
install:
    uv sync --directory backend --locked --group screenshots
    npm --prefix frontend ci
    pre-commit install --install-hooks

# ---------------------------------------------------------------- database

# Apply migrations up to a revision
migrate revision="head":
    {{ backend }} alembic upgrade {{ revision }}

# Roll migrations back to a revision (default: one step; `base` for an empty schema)
downgrade revision="-1":
    {{ backend }} alembic downgrade {{ revision }}

# Drop and recreate the dev schema (deletes all synced data)
[confirm("This deletes all data in the dev database. Continue?")]
db-reset:
    {{ backend }} alembic downgrade base
    {{ backend }} alembic upgrade head

# ---------------------------------------------------------------- run (each in its own terminal)

# Start the API with auto-reload on http://127.0.0.1:8000
api:
    {{ backend }} copilot-metrics api --reload

# Start the sync worker
worker:
    {{ backend }} copilot-metrics worker

# Re-fetch all history, synced or not (the worker already catches up on start)
backfill:
    {{ backend }} copilot-metrics backfill

# Start the Vite dev server on http://localhost:5173
web:
    npm --prefix frontend run dev

# ---------------------------------------------------------------- quality

# Formatting, lint and type checks on all files (the pre-commit hook)
check:
    pre-commit run --all-files

# Backend and frontend tests
test:
    {{ backend }} pytest
    npm --prefix frontend test

# Run the CI test suites in containers, as CI does (needs Docker)
ci-test:
    docker compose -f ci/compose.yaml run --rm --build backend-test
    docker compose -f ci/compose.yaml run --rm --build frontend-test
    docker compose -f ci/compose.yaml down -v

# Build the production image and smoke-test it, as CI does (needs Docker)
image tag="copilot-usage:local":
    docker build --target app -t {{ tag }} .
    ci/smoke-test.sh {{ tag }}

# ---------------------------------------------------------------- docs (see tools/screenshots/README.md)

# Playwright is locked in backend/uv.lock (dependency group `screenshots`).
playwright := "uv run --directory backend --group screenshots"

# Outside the dev container only (it ships Playwright's Chromium): install it, or Debian's
# where Playwright's download host is blocked
screenshots-setup:
    {{ playwright }} playwright install --with-deps chromium || { echo "==> Playwright's download failed; installing Debian's chromium instead"; sudo apt-get update -qq && sudo apt-get install -y --no-install-recommends chromium; }

# Regenerate docs/images/ from fictional demo data (e.g. `just screenshots --only my-usage`)
screenshots *args:
    npm --prefix frontend run build
    {{ playwright }} python ../tools/screenshots/screenshots.py {{ args }}

# ---------------------------------------------------------------- release (see docs/releasing.md)

# Tag the current main commit as v<version> (e.g. 1.4.0, 1.5.0rc1) and push it; or use Actions > Release > Run workflow
release version:
    #!/usr/bin/env bash
    set -euo pipefail
    version="{{ version }}"
    version="${version#v}"
    tag="v$version"
    n='(0|[1-9][0-9]*)'
    [[ "$version" =~ ^$n\.$n\.$n((a|b|rc)$n|\.dev$n)?$ ]] || { echo "Use X.Y.Z, optionally followed by aN, bN, rcN or .devN (e.g. 1.4.0, 1.5.0rc1)." >&2; exit 1; }
    [[ "$(git branch --show-current)" == main ]] || { echo "Switch to main first." >&2; exit 1; }
    [[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "Commit or stash your changes first." >&2; exit 1; }
    git fetch --quiet --tags origin main
    [[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || { echo "main is not in sync with origin/main; pull or push first." >&2; exit 1; }
    ! git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null || { echo "$tag already exists; releases can't be overwritten." >&2; exit 1; }
    read -rp "Tag $(git rev-parse --short HEAD) as $tag and push it (starts the Release workflow)? [y/N] " answer
    [[ "$answer" == [yY] ]] || exit 1
    git tag -a "$tag" -m "Release $tag"
    git push origin "$tag"
    echo "Release workflow: https://github.com/InsaneDwayne/copilot-user-metrics/actions/workflows/release.yml"
