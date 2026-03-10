#!/bin/bash
. ~/.claude/env

cd "$VAULT_DIR"
python ~/.claude/skills/recall/scripts/extract-sessions.py --days 3 --source ~/.claude/projects
qmd update
