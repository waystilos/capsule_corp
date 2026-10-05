# scripts/install_elixir.ps1 - Windows PowerShell Installer for Elixir & Erlang
# Elixir is an optional installer only; the Capsule Corp agent system does not use it at runtime.
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Yes,
    [switch]$Json,
    [string]$Manager,
    [string]$Version
)

$ErrorActionPreference = "Stop"
$Note = "Elixir/Erlang is an optional installer only; the agent system does not use it at runtime."

if ($Version -and $Version -cnotmatch '^[0-9][0-9A-Za-z.+_-]*\z') {
    [Console]::Error.WriteLine("Error: invalid -Version; must match [0-9][0-9A-Za-z.+_-]* (e.g. 1.17.3).")
    exit 2
}

# If python is available, delegate to install_elixir.py for unified handling
if (Get-Command python -ErrorAction SilentlyContinue) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $pyScript = Join-Path $scriptDir "install_elixir.py"
    $pyArgs = @()
    if ($DryRun) { $pyArgs += "--dry-run" }
    if ($Force) { $pyArgs += "--force" }
    if ($Yes) { $pyArgs += "-y" }
    if ($Json) { $pyArgs += "--json" }
    if ($Manager) { $pyArgs += @("--manager", $Manager) }
    if ($Version) { $pyArgs += @("--version", $Version) }
    & python $pyScript $pyArgs
    exit $LASTEXITCODE
}

function Write-Result($status, $message, $commands) {
    if ($Json) {
        $obj = [ordered]@{ status = $status; message = $message; note = $Note }
        if ($commands) { $obj["commands"] = @($commands) }
        $obj | ConvertTo-Json -Depth 4
    } else {
        Write-Host $message
    }
}

# Native PowerShell fallback (Python missing)
if ($Manager -or $Version) {
    Write-Result "error" "-Manager/-Version require Python 3; install Python or run the package manager yourself." $null
    exit 2
}
if ((Get-Command elixir -ErrorAction SilentlyContinue) -and -not $Force) {
    Write-Result "already_installed" "Elixir is already installed on this Windows system. Use -Force to reinstall." $null
    if (-not $Json) { elixir --version }
    exit 0
}

if (Get-Command winget -ErrorAction SilentlyContinue) {
    $name = "winget"
    $cmdLine = "winget install ErlangSolutions.Elixir --accept-package-agreements --accept-source-agreements"
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    $name = "chocolatey"
    $cmdLine = "choco install -y elixir"
} elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
    $name = "scoop"
    $cmdLine = "scoop install elixir"
} else {
    Write-Result "error" "No supported Windows package manager (winget, choco, scoop) was found. Install one or download Elixir from https://elixir-lang.org/install.html#windows" $null
    exit 1
}

if ($DryRun) {
    Write-Result "dry_run" "Dry run ($name): $cmdLine. $Note" @($cmdLine)
    exit 0
}

if (-not $Yes) {
    Write-Result "error" "Refusing to install without -Yes. Plan ($name): $cmdLine. Re-run with -Yes to proceed or -DryRun to preview." @($cmdLine)
    exit 1
}

if (-not $Json) { Write-Host "==> Installing Elixir via ${name}: $cmdLine" -ForegroundColor Cyan }
switch ($name) {
    "winget" { winget install ErlangSolutions.Elixir --accept-package-agreements --accept-source-agreements }
    "chocolatey" { choco install -y elixir }
    "scoop" { scoop install elixir }
}
$code = $LASTEXITCODE
if ($null -ne $code -and $code -ne 0) {
    Write-Result "failed" "Installer exited with code $code" @($cmdLine)
    exit $code
}
Write-Result "success" "Elixir installation completed. Restart your PowerShell session. $Note" @($cmdLine)
exit 0
