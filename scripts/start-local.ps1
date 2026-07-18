[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [switch]$Reload,
    [switch]$RebuildFrontend,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$frontendDist = Join-Path $frontendDir "dist"
$frontendIndex = Join-Path $frontendDist "index.html"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) {
    $venvPython
} else {
    (Get-Command python -ErrorAction Stop).Source
}

if (-not $SkipFrontendBuild -and ($RebuildFrontend -or -not (Test-Path -LiteralPath $frontendIndex))) {
    $npm = (Get-Command npm -ErrorAction Stop).Source
    Write-Host "Building the hosted frontend..."
    Push-Location $frontendDir
    try {
        & $npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $frontendIndex)) {
    Write-Warning "No frontend build was found. The API will start, but /ui/ will not be hosted. Run npm install then .\scripts\start-local.ps1 -RebuildFrontend."
}
if (-not $env:APISWITCH_MASTER_KEY) {
    Write-Warning "APISWITCH_MASTER_KEY is not set. Configure it before saving provider credentials, OAuth tokens, or WebDAV passwords."
}

$env:APISWITCH_LISTEN_HOST = "127.0.0.1"
$env:APISWITCH_PORT = "$Port"
$env:APISWITCH_FRONTEND_DIST_DIR = $frontendDist
$env:APISWITCH_RELOAD = if ($Reload) { "true" } else { "false" }

Write-Host "Starting APISwitch at http://127.0.0.1:$Port (UI: /ui/, API docs: /docs)"
Push-Location $backendDir
try {
    & $python -m apiswitch
} finally {
    Pop-Location
}
