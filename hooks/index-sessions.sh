#!/bin/bash
set -euo pipefail

# ir indexes Claude-Sessions/ directly (kept current by sync hook)
# No extraction step needed — just update the search index
if command -v ir >/dev/null 2>&1; then
    ir update
fi
