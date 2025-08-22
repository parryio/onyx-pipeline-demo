#!/usr/bin/env bash
set -euo pipefail

LIB="tests/fixtures_long"
FIXTURE="$LIB/scanned_book.pdf"

if [[ ! -f "$FIXTURE" ]]; then
  echo "long demo skipped: missing $FIXTURE"
  exit 0
fi

OUT="runs/long"
if [[ "${CI:-}" != "true" && "${1:-}" != "--fixed" ]]; then
  OUT="runs/long-$(date +%Y%m%d-%H%M%S)"
fi

rm -rf "$OUT"
onyx-manifest build --lib "$LIB" --out "$OUT"
onyx-pipeline run --lib "$LIB" --out "$OUT" --ocr-lang eng --include-images
onyx-validate --out "$OUT"

echo "summary: $OUT/reports/run_summary.json"
