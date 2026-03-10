#!/bin/bash
set -euo pipefail

. ~/.claude/env

if [ -z "${VAULT_DIR:-}" ] || [ ! -d "$VAULT_DIR" ]; then
    echo "Error: VAULT_DIR not set or not a directory: '${VAULT_DIR:-}'" >&2
    exit 1
fi

cd "$VAULT_DIR"
python3 ~/.claude/skills/recall/scripts/extract-sessions.py --days 3 --source ~/.claude/projects

# QMD index update (skip if qmd not installed)
if command -v qmd >/dev/null 2>&1; then
    qmd update
fi
