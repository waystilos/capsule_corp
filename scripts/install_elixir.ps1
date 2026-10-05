# scripts/install_elixir.ps1 - Windows PowerShell Installer for Elixir & Erlang
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

# If python is available, delegate to install_elixir.py for unified handling
if (Get-Command python -ErrorAction SilentlyContinue) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $pyScript = Join-Path $scriptDir "install_elixir.py"
    $pyArgs = @()
    if ($DryRun) { $pyArgs += "--dry-run" }
    if ($Force) { $pyArgs += "--force" }
    if ($Yes) { $pyArgs += "-y" }
    & python $pyScript $pyArgs
    exit $LASTEXITCODE
}

# Native PowerShell fallback
if ((Get-Command elixir -ErrorAction SilentlyContinue) -and -not $Force) {
    Write-Host "✓ Elixir is already installed on this Windows system." -ForegroundColor Green
    elixir --version
    exit 0
}

Write-Host "==> Detecting Windows package manager..." -ForegroundColor Cyan

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "==> Installing Elixir via winget..." -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "Dry run: winget install ErlangSolutions.Elixir --accept-package-agreements --accept-source-agreements"
        exit 0
    }
    winget install ErlangSolutions.Elixir --accept-package-agreements --accept-source-agreements
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "==> Installing Elixir via Chocolatey..." -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "Dry run: choco install -y elixir"
        exit 0
    }
    choco install -y elixir
} elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
    Write-Host "==> Installing Elixir via Scoop..." -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "Dry run: scoop install elixir"
        exit 0
    }
    scoop install elixir
} else {
    Write-Error "No supported Windows package manager (winget, choco, scoop) was found. Please install winget or download Elixir from https://elixir-lang.org/install.html#windows"
    exit 1
}

Write-Host "✓ Elixir installation completed. Please restart your PowerShell session." -ForegroundColor Green
