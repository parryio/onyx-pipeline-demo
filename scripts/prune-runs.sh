#!/usr/bin/env bash
set -euo pipefail
echo "Pruning run dirs older than 7 days under runs/"
find runs -maxdepth 1 -type d -name '20*' -mtime +7 -print -exec rm -rf {} + 2>/dev/null || true
