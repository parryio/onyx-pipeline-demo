param(
    [switch]$Quick,
    [int]$MaxDocs = 0,
    [switch]$SkipBuild,
    [switch]$NoLaunch,
    [string]$ConfigPath = "config\onyx.yml",
    [string]$ArtifactsDir = "artifacts",
    [string]$RootDir = "Library",
    [string]$AppDir = "onyx-hall-phase5-app"
)

# Strict and fail-fast
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host "[info] $msg" -ForegroundColor DarkGray }
function Write-Ok($msg)   { Write-Host "[ok]   $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[err]  $msg" -ForegroundColor Red }

# Resolve repo root from script location
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot
Write-Info "Repo root: $RepoRoot"

# Determinism: pin Python hash seed for all child processes
$env:PYTHONHASHSEED = "0"
Write-Info "PYTHONHASHSEED=$($env:PYTHONHASHSEED)"

# Optional quick mode for Phase 1 (limit docs)
if ($Quick) {
    if ($MaxDocs -le 0) { $MaxDocs = 200 }
    $env:ONYX_PHASE1_MAX_DOCS = "$MaxDocs"
    Write-Info "Quick mode: ONYX_PHASE1_MAX_DOCS=$($env:ONYX_PHASE1_MAX_DOCS)"
}

# Helper to run Python CLI for each phase
function Invoke-Phase([string]$phase, [string[]]$extraArgs = @()) {
    $common = @('-m','onyx_scribe.cli', $phase, '--config', $ConfigPath, '--root', $RootDir, '--artifacts', $ArtifactsDir) + $extraArgs
    Write-Info "python $($common -join ' ')"
    & python @common
}

# Build artifacts (Phases 1-5) unless skipped
if (-not $SkipBuild) {
    Write-Step "Building artifacts (Phases 1-5)"
    Invoke-Phase 'phase1'
    Invoke-Phase 'phase2'
    # Phase 3 (golden_pipeline) is invoked via onyx_scribe CLI as per repo's orchestrator
    Invoke-Phase 'phase3'
    # Assemble kits (phase 4)
    Invoke-Phase 'assemble_kits'
    # Phase 5 artifact export (UI data + assets manifest)
    Invoke-Phase 'phase5'
    Write-Ok "Artifacts rebuilt under '$ArtifactsDir'"
} else {
    Write-Info "Skipping build (-SkipBuild)"
}

# Ensure phase5 folder exists (for junction target)
$ArtifactsPhase5 = Join-Path $RepoRoot (Join-Path $ArtifactsDir 'phase5')
if (-not (Test-Path $ArtifactsPhase5)) {
    New-Item -ItemType Directory -Force -Path $ArtifactsPhase5 | Out-Null
    Write-Info "Created: $ArtifactsPhase5"
}

# Refresh junction so the packaged app uses repo artifacts
Write-Step "Refreshing AppData junction to phase5 artifacts"
$AppDataDir = Join-Path $env:APPDATA 'onyx-hall-phase5-app\artifacts\phase5'
Write-Info "AppData phase5 path: $AppDataDir"

# Remove any existing folder/junction (works for both types)
if (Test-Path $AppDataDir) {
    Write-Info "Removing existing junction/folder at: $AppDataDir"
    # Use rmdir /S /Q to handle both regular directories and junctions
    & cmd /c "rmdir /S /Q \"$AppDataDir\"" | Out-Null
    Start-Sleep -Milliseconds 100
    if (Test-Path $AppDataDir) {
        throw "Unable to remove existing path: $AppDataDir. Close any running app that may be locking it, then retry."
    }
}

# Create a junction pointing to repo artifacts/phase5 (use absolute path for robustness)
$TargetAbs = (Resolve-Path $ArtifactsPhase5).Path
Write-Info "Junction target: $TargetAbs"
& cmd /c "mklink /J \"$AppDataDir\" \"$TargetAbs\"" | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $AppDataDir)) {
    throw "mklink failed to create junction: $AppDataDir -> $TargetAbs (exit=$LASTEXITCODE)"
}
try {
    $item = Get-Item -LiteralPath $AppDataDir -Force
    if (-not ($item.Attributes.ToString() -match 'ReparsePoint')) {
        throw "Created path is not a junction (reparse point): $AppDataDir"
    }
} catch {
    throw $_
}
Write-Ok "Junction set: $AppDataDir -> $TargetAbs"

if ($NoLaunch) {
    Write-Info "No launch requested (-NoLaunch). Done."
    return
}

# Launch Electron dev app
Write-Step "Launching Electron dev app"
$AppPath = Join-Path $RepoRoot $AppDir
if (-not (Test-Path $AppPath)) {
    throw "App directory not found: $AppPath"
}
Push-Location $AppPath
try {
    if (-not (Test-Path (Join-Path $AppPath 'node_modules'))) {
        Write-Info "node_modules missing - running 'npm install'"
        & npm install
    }
    Write-Info "Starting dev server: npm run dev"
    & npm run dev
} finally {
    Pop-Location | Out-Null
}
