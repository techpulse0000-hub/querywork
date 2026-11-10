param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Run Setup.ps1 first.' }
if (-not (Test-Path 'dist/index.html')) { throw 'Run Setup.ps1 to build the interface.' }
$ready = $false
try { $schema = Invoke-RestMethod 'http://127.0.0.1:8766/openapi.json' -TimeoutSec 2; $ready = $schema.info.title -eq 'Querywork local API'; if (-not $ready) { throw 'Port 8766 is occupied by another app.' } } catch { if ($_.Exception.Message -like '*occupied*') { throw } }
if (-not $ready) {
    Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8766' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $schema = Invoke-RestMethod 'http://127.0.0.1:8766/openapi.json' -TimeoutSec 2; $ready = $schema.info.title -eq 'Querywork local API'; if ($ready) { break } } catch {}
    }
}
if (-not $ready) { throw 'Service did not start. Run .venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8766 to view diagnostics.' }
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8766' }

