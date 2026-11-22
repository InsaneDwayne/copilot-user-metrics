#!/usr/bin/env bash
# Installs backend and frontend dependencies and the git hooks, then checks the database is up.
set -euo pipefail
cd /workspace

just install

echo "==> database"
pg_isready -h db -U copilot && psql -c "select version();" -tA
