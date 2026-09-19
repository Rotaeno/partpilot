$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:PIP_CACHE_DIR | Out-Null
if (!(Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
$req = if (Test-Path 'requirements.lock.txt') { 'requirements.lock.txt' } else { 'requirements.txt' }
& ./.venv/Scripts/python.exe -m pip install -r $req --disable-pip-version-check
exit $LASTEXITCODE
