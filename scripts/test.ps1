[CmdletBinding()]
param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
$npm = (Get-Command npm -ErrorAction Stop).Source

Push-Location $backendDir
try {
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}

Push-Location $frontendDir
try {
    & $npm run test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed with exit code $LASTEXITCODE." }
    if (-not $SkipFrontendBuild) {
        & $npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
    }
} finally {
    Pop-Location
}
