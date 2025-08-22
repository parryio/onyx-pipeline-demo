Param(
  [switch]$Fixed
)
$ErrorActionPreference = 'Stop'
$lib = 'tests/fixtures_long'
$pdf = Join-Path $lib 'scanned_book.pdf'
if (-not (Test-Path $pdf)) { Write-Error "Missing $pdf" }

if ($Env:CI -or $Fixed) {
  $out = "runs/long"
  if (Test-Path $out) { Remove-Item -Recurse -Force $out }
  New-Item -ItemType Directory -Force -Path $out | Out-Null
} else {
  $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
  $out = "runs/$ts-long"
}
Write-Host "[long] output: $out"
onyx-manifest build --lib $lib --out $out
onyx-pipeline run --lib $lib --out $out --ocr-lang eng --include-images
onyx-validate --out $out
if (Test-Path "$out/reports/run_summary.json") { Get-Content "$out/reports/run_summary.json" }
