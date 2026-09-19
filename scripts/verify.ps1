param([switch]$WithUI)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path '.tmp','artifacts' | Out-Null
& ./.venv/Scripts/python.exe scripts/generate_catalog.py --check
if ($LASTEXITCODE) { throw 'Catalog verification failed' }
& ./.venv/Scripts/python.exe scripts/fetch_public_data.py --verify-only
if ($LASTEXITCODE) { throw 'Public source verification failed' }
& ./.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/tests-final.xml
if ($LASTEXITCODE) { throw 'Backend tests failed' }
& ./.venv/Scripts/python.exe scripts/evaluate.py
if ($LASTEXITCODE) { throw 'Offline evaluation failed' }
if ($WithUI) {
    node --check static/app.js
    if ($LASTEXITCODE) { throw 'JavaScript syntax failed' }
    node scripts/test_ui.cjs
    if ($LASTEXITCODE) { throw 'DOM/API integration failed' }
}
Write-Output 'This verification command makes no external model calls. Live research UI/evaluation require explicit separate commands. DOM testing is not visual browser verification.'
