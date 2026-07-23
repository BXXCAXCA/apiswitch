[CmdletBinding()]
param(
    [string]$Executable = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "dist\APISwitch.exe")
)

$ErrorActionPreference = "Stop"
$executablePath = (Resolve-Path -LiteralPath $Executable).Path
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$reports = Join-Path $root "dist\diagnostics"
$diagnosticHome = Join-Path ([IO.Path]::GetTempPath()) ("apiswitch-ci-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $reports -Force | Out-Null
New-Item -ItemType Directory -Path $diagnosticHome -Force | Out-Null

$previousUserProfile = $env:USERPROFILE
$firstProbe = $null

function Wait-ForReport {
    param([string]$Path, [int]$TimeoutSeconds = 45)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $Path -PathType Leaf) { return }
        Start-Sleep -Milliseconds 200
    }
    throw "Timed out waiting for diagnostic report: $Path"
}

function Invoke-Diagnostic {
    param([string[]]$Arguments, [string]$ReportPath)
    if (Test-Path -LiteralPath $ReportPath) { Remove-Item -LiteralPath $ReportPath -Force }
    $process = Start-Process -FilePath $executablePath -ArgumentList $Arguments -PassThru -Wait
    Wait-ForReport -Path $ReportPath
    if ($process.ExitCode -ne 0) {
        $body = Get-Content -LiteralPath $ReportPath -Raw
        throw "APISwitch diagnostic exited with $($process.ExitCode): $body"
    }
    return Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
}

try {
    $env:USERPROFILE = $diagnosticHome

    $smokeReport = Join-Path $reports "smoke-default.json"
    $smoke = Invoke-Diagnostic -Arguments @("--smoke-test", "--report", ('"{0}"' -f $smokeReport)) -ReportPath $smokeReport
    if (-not $smoke.ok -or $smoke.health_status -ne 200 -or $smoke.ui_status -ne 200 -or -not $smoke.ui_has_app_root) {
        throw "Default packaged smoke test failed: $($smoke | ConvertTo-Json -Depth 8)"
    }

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8080)
    $listener.Start()
    try {
        $fallbackReport = Join-Path $reports "smoke-port-conflict.json"
        $fallback = Invoke-Diagnostic -Arguments @("--smoke-test", "--report", ('"{0}"' -f $fallbackReport)) -ReportPath $fallbackReport
        if (-not $fallback.ok -or $fallback.port -eq 8080 -or -not $fallback.used_fallback_port) {
            throw "Port-conflict fallback test failed: $($fallback | ConvertTo-Json -Depth 8)"
        }
    } finally {
        $listener.Stop()
    }

    $firstReport = Join-Path $reports "instance-first.json"
    $secondReport = Join-Path $reports "instance-second.json"
    foreach ($path in @($firstReport, $secondReport)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }

    $firstProbe = Start-Process -FilePath $executablePath -ArgumentList @(
        "--instance-probe",
        "--report",
        ('"{0}"' -f $firstReport),
        "--hold-seconds",
        "20"
    ) -PassThru
    Wait-ForReport -Path $firstReport
    $first = Get-Content -LiteralPath $firstReport -Raw | ConvertFrom-Json
    if (-not $first.acquired) { throw "The first packaged process did not acquire the single-instance mutex." }

    $second = Invoke-Diagnostic -Arguments @(
        "--instance-probe",
        "--report",
        ('"{0}"' -f $secondReport)
    ) -ReportPath $secondReport
    if ($second.acquired) { throw "The second packaged process incorrectly acquired the single-instance mutex." }

    if (-not $firstProbe.WaitForExit(30000)) {
        $firstProbe.Kill()
        throw "The first single-instance probe did not exit cleanly."
    }
    if ($firstProbe.ExitCode -ne 0) { throw "The first single-instance probe exited with $($firstProbe.ExitCode)." }

    Write-Host "Packaged desktop verification passed."
    Get-ChildItem -LiteralPath $reports -Filter *.json | ForEach-Object {
        Write-Host "--- $($_.Name)"
        Get-Content -LiteralPath $_.FullName
    }
} finally {
    if ($firstProbe -and -not $firstProbe.HasExited) { $firstProbe.Kill() }
    $env:USERPROFILE = $previousUserProfile
    Remove-Item -LiteralPath $diagnosticHome -Recurse -Force -ErrorAction SilentlyContinue
}
