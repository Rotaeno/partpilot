param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1
exit $LASTEXITCODE
