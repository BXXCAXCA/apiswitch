Set-Location "$PSScriptRoot\..\backend"
pytest
Set-Location "$PSScriptRoot\..\frontend"
npm run test
