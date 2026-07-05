@echo off
:: ══════════════════════════════════════════════════════════════════
::  run_local.bat  -  Double-click launcher for ResumaticAI
::  Calls run_local.ps1 with the correct PowerShell execution policy.
:: ══════════════════════════════════════════════════════════════════

cd /d "%~dp0"

:: Use %* instead of %1 to safely forward all operational arguments
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [local] Script exited with error code %ERRORLEVEL%
    echo [local] Press any key to close this window.
    pause >nul
)