Write-Host "Starting APISwitch backend and frontend in separate PowerShell windows..."
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\frontend.ps1"
