<#!
.
SYNOPSIS
    Sync Phase 5 artifacts into the app's user data folder so the packaged app loads your real dataset.

DESCRIPTION
    Copies files from your repository's artifacts/phase5 (or a provided source) into
    %APPDATA%\onyx-hall-phase5-app\artifacts\phase5, which is the highest-priority
    location the app checks at runtime.

PARAMETERS
    -Source   Optional. Source folder containing ui_catalog.jsonl, assets_manifest.jsonl, etc.
              Defaults to <repo_root>\artifacts\phase5.
    -Target   Optional. Destination folder. Defaults to %APPDATA%\onyx-hall-phase5-app\artifacts\phase5.

EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\sync_phase5_artifacts.ps1
    powershell -ExecutionPolicy Bypass -File .\scripts\sync_phase5_artifacts.ps1 -Source C:\data\phase5
!#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$Source,

    [Parameter(Mandatory=$false)]
    [string]$Target
)

$ErrorActionPreference = 'Stop'

try {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..') | Select-Object -ExpandProperty Path
    if (-not $Source -or [string]::IsNullOrWhiteSpace($Source)) {
        $Source = Join-Path $repoRoot 'artifacts\phase5'
    }
    if (-not $Target -or [string]::IsNullOrWhiteSpace($Target)) {
        $Target = Join-Path $env:APPDATA 'onyx-hall-phase5-app\artifacts\phase5'
    }

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source not found: $Source"
    }

    Write-Host "Source: $Source"
    Write-Host "Target: $Target"

    # Create destination directory
    $null = New-Item -ItemType Directory -Force -Path $Target

    # Copy files
    Copy-Item -Path (Join-Path $Source '*') -Destination $Target -Recurse -Force

    # Small verification of expected files
    $expected = @('ui_catalog.jsonl','assets_manifest.jsonl')
    $missing = @()
    foreach ($f in $expected) {
        if (-not (Test-Path -LiteralPath (Join-Path $Target $f))) { $missing += $f }
    }

    if ($missing.Count -gt 0) {
        Write-Warning ("Sync completed, but missing expected files in target: {0}" -f ($missing -join ', '))
    } else {
        Write-Host "Sync complete. Expected files present." -ForegroundColor Green
    }

    Write-Host "App will prioritize this folder at runtime: $Target"
}
catch {
    Write-Error $_
    exit 1
}
