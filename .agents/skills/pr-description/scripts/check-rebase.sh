#!/bin/bash

# Check if current branch is rebased on origin/main
# Usage: bash check-rebase.sh

set -e

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
ORIGIN_MAIN=$(git rev-parse origin/main)
HEAD=$(git rev-parse HEAD)

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "HEAD" ]; then
  echo "❌ ERROR: You're on '$CURRENT_BRANCH'. Switch to your feature branch first."
  exit 1
fi

# Fetch latest to ensure we have latest origin/main
git fetch origin main 2>/dev/null || true

ORIGIN_MAIN=$(git rev-parse origin/main)
HEAD=$(git rev-parse HEAD)
MERGE_BASE=$(git merge-base HEAD origin/main)

if [ "$MERGE_BASE" != "$ORIGIN_MAIN" ]; then
  echo "⚠️  Branch not rebased on origin/main"
  echo ""
  echo "Your branch '$CURRENT_BRANCH' needs rebase:"
  echo "  git rebase origin/main"
  echo ""
  exit 1
fi

echo "✅ Branch '$CURRENT_BRANCH' is rebased on origin/main"
echo ""
echo "Git diff summary (origin/main..HEAD):"
git diff --stat origin/main HEAD
