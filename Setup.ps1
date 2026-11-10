$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonCommand = 'python'
$installedPython = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'
if (Test-Path -LiteralPath $installedPython) { $pythonCommand = $installedPython }
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    & $pythonCommand -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed. Install Python 3.12+ and retry.' }
}
& $pythonCommand -m pip --python .venv/Scripts/python.exe install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
npm.cmd ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Output 'Ready. Open Launch.cmd to start Querywork.'
