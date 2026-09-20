@echo off
setlocal
title PartPilot - local server
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -Online -BudgetCny 50
echo.
echo Open http://127.0.0.1:8765/ in your browser while the server is running.
echo If startup failed, read the error above.
pause
