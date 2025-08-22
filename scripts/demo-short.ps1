Param(
  [switch]$Fixed
)
$ErrorActionPreference = 'Stop'

if ($Env:CI -or $Fixed) {
  $out = "runs/short"
  if (Test-Path $out) { Remove-Item -Recurse -Force $out }
  New-Item -ItemType Directory -Force -Path $out | Out-Null
} else {
  $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
  $out = "runs/$ts-short"
}
Write-Host "[short] output: $out"
onyx-manifest build --lib tests/fixtures --out $out
onyx-pipeline run --lib tests/fixtures --out $out --ocr-lang eng --include-images
onyx-validate --out $out
if (Test-Path "$out/reports/run_summary.json") { Get-Content "$out/reports/run_summary.json" }
