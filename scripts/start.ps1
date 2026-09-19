param([int]$Port = 8765, [switch]$Online, [double]$BudgetCny = 50)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
if ($Online) {
    if ($BudgetCny -le 0 -or $BudgetCny -gt 50) { throw 'Online budget must be above zero and at most the authorized CNY 50.' }
    $env:PARTPILOT_MODE = 'qwen'
    $env:PARTPILOT_ENABLE_PAID_API = 'true'
    $env:PARTPILOT_BUDGET_CNY = $BudgetCny.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    $env:PARTPILOT_MAX_CALLS = '200'
    $env:PARTPILOT_MAX_OUTPUT_TOKENS = '1200'
} else {
    $env:PARTPILOT_MODE = 'demo'
    $env:PARTPILOT_ENABLE_PAID_API = 'false'
    $env:PARTPILOT_BUDGET_CNY = '0'
}
& ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1
exit $LASTEXITCODE
