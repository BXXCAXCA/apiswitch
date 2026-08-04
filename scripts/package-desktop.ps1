[CmdletBinding()]
param([switch]$Clean)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"
$pyinstaller = Join-Path $backend ".venv\Scripts\pyinstaller.exe"
$stageDist = Join-Path $root "build\desktop-dist"
. (Join-Path $PSScriptRoot "version.ps1")
$version = Get-APISwitchVersion -RepositoryRoot $root
$destinationExe = Join-Path $root "dist\APISwitch-v$version.exe"
$legacyExe = Join-Path $root "dist\APISwitch.exe"
if (-not (Test-Path -LiteralPath $pyinstaller)) { $pyinstaller = (Get-Command pyinstaller -ErrorAction Stop).Source }
function Get-ViteEnvironment {
    # `set PREFIX` returns exit code 1 when no matching variables exist.
    # That is a valid clean-build state, so normalize it to an empty result.
    $output = & cmd.exe /d /c "set VITE_ 2>nul & exit /b 0"
    foreach ($line in $output) {
        $separator = $line.IndexOf('=')
        if ($separator -gt 0) {
            [PSCustomObject]@{ Name = $line.Substring(0, $separator); Value = $line.Substring($separator + 1) }
        }
    }
}
function Clear-ViteEnvironment {
    foreach ($entry in (Get-ViteEnvironment)) {
        [Environment]::SetEnvironmentVariable($entry.Name, $null, 'Process')
    }
}
$viteEnvironment = @(Get-ViteEnvironment)
Push-Location $frontend
try {
    Clear-ViteEnvironment
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Clear-ViteEnvironment
    foreach ($entry in $viteEnvironment) { Set-Item ("Env:" + $entry.Name) $entry.Value }
    Pop-Location
}
Push-Location $root
try {
    $legacyOnedir = Join-Path $root "dist\APISwitch"
    if ($Clean -and (Test-Path -LiteralPath $legacyOnedir -PathType Container)) {
        $resolvedLegacyOnedir = (Resolve-Path -LiteralPath $legacyOnedir).Path
        $expectedDist = (Join-Path $root "dist") + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedLegacyOnedir.StartsWith($expectedDist, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected legacy output path: $resolvedLegacyOnedir"
        }
        Remove-Item -LiteralPath $resolvedLegacyOnedir -Recurse -Force
    }
    $arguments = @("--noconfirm", "--onefile", "--windowed", "--name", "APISwitch", "--distpath", $stageDist, "--paths", $backend, "--collect-submodules", "apiswitch", "--hidden-import", "pystray._win32", "--collect-submodules", "PIL", "--exclude-module", "IPython", "--add-data", "$frontend\dist;frontend\dist")
    if ($Clean) { $arguments += "--clean" }
    $arguments += "$backend\apiswitch\desktop_entry.py"
    & $pyinstaller @arguments
    if ($LASTEXITCODE -ne 0) { throw "Desktop packaging failed." }
    $stagedExe = Join-Path $stageDist "APISwitch.exe"
    if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf)) { throw "Staged desktop executable is missing." }
    $destinationDirectory = Split-Path -Parent $destinationExe
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    $replaceTargets = @($destinationExe, $legacyExe) | ForEach-Object { [IO.Path]::GetFullPath($_) }
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $replaceTargets -contains [IO.Path]::GetFullPath($_.Path) } |
        Stop-Process -Force
    Start-Sleep -Milliseconds 300
    if (Test-Path -LiteralPath $legacyExe -PathType Leaf) {
        Remove-Item -LiteralPath $legacyExe -Force
    }
    Move-Item -LiteralPath $stagedExe -Destination $destinationExe -Force
    Write-Host "Packaged APISwitch v${version}: $destinationExe"
} finally { Pop-Location }
