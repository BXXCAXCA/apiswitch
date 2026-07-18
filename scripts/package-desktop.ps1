[CmdletBinding()]
param([switch]$Clean)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"
$pyinstaller = Join-Path $backend ".venv\Scripts\pyinstaller.exe"
$stageDist = Join-Path $root "build\desktop-dist"
$destinationExe = Join-Path $root "dist\APISwitch.exe"
if (-not (Test-Path -LiteralPath $pyinstaller)) { $pyinstaller = (Get-Command pyinstaller -ErrorAction Stop).Source }
$viteEnvironment = @(Get-ChildItem Env: | Where-Object { $_.Name -like "VITE_*" } | ForEach-Object { [PSCustomObject]@{ Name = $_.Name; Value = $_.Value } })
Push-Location $frontend
try {
    Get-ChildItem Env: | Where-Object { $_.Name -like "VITE_*" } | ForEach-Object { Remove-Item ("Env:" + $_.Name) -ErrorAction SilentlyContinue }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Get-ChildItem Env: | Where-Object { $_.Name -like "VITE_*" } | ForEach-Object { Remove-Item ("Env:" + $_.Name) -ErrorAction SilentlyContinue }
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
    $arguments += "$backend\apiswitch\desktop.py"
    & $pyinstaller @arguments
    if ($LASTEXITCODE -ne 0) { throw "Desktop packaging failed." }
    $stagedExe = Join-Path $stageDist "APISwitch.exe"
    if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf)) { throw "Staged desktop executable is missing." }
    $destinationDirectory = Split-Path -Parent $destinationExe
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    Get-Process -Name "APISwitch" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and [IO.Path]::GetFullPath($_.Path).Equals([IO.Path]::GetFullPath($destinationExe), [StringComparison]::OrdinalIgnoreCase) } |
        Stop-Process -Force
    Start-Sleep -Milliseconds 300
    Move-Item -LiteralPath $stagedExe -Destination $destinationExe -Force
} finally { Pop-Location }
