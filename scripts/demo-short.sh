#!/usr/bin/env bash
set -euo pipefail

OUT="runs/short"
if [[ "${CI:-}" != "true" && "${1:-}" != "--fixed" ]]; then
  OUT="runs/short-$(date +%Y%m%d-%H%M%S)"
fi

rm -rf "$OUT"
onyx-manifest build --lib tests/fixtures --out "$OUT"
onyx-pipeline run --lib tests/fixtures --out "$OUT" --ocr-lang eng --include-images
onyx-validate --out "$OUT"

echo "summary: $OUT/reports/run_summary.json"
