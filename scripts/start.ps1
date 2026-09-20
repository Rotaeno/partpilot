param([ValidateRange(1, 65535)][int]$Port = 8765, [switch]$Online, [double]$BudgetCny = 50)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
if (-not (Test-Path -LiteralPath './.venv/Scripts/python.exe')) {
    throw 'Project dependencies are missing. Run .\scripts\setup.ps1 first.'
}
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
$url = "http://127.0.0.1:$Port"
$existing = $null
try {
    $existing = Invoke-RestMethod "$url/openapi.json" -TimeoutSec 2
} catch { }
if ($null -ne $existing) {
    if ($existing.info.title -ne 'PartPilot') {
        throw "Port $Port belongs to another application. Choose a different -Port."
    }
    $current = Invoke-RestMethod "$url/api/research/config" -TimeoutSec 2
    $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 2
    if ($health.mode -ne $env:PARTPILOT_MODE -or ($Online -and $current.budget_cny -ne $BudgetCny)) {
        throw "PartPilot is already running with different settings. Stop its server before changing mode or budget."
    }
    Write-Host "PartPilot is already running. Open $url in your browser."
    exit 0
}
if ($Online -and [string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
    throw 'DASHSCOPE_API_KEY is missing from this terminal. Set the environment variable, or run without -Online for demo mode.'
}
Write-Host "PartPilot: $url"
Write-Host "Mode: $env:PARTPILOT_MODE. Keep this window open while using the app. Ctrl+C stops the server."
& ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1
exit $LASTEXITCODE
