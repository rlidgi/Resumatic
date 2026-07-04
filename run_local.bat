@echo off
:: ══════════════════════════════════════════════════════════════════
::  run_local.bat  -  Double-click launcher for ResumaticAI
::  Calls run_local.ps1 with the correct PowerShell execution policy.
:: ══════════════════════════════════════════════════════════════════
::
::  USAGE (from cmd.exe or double-click in Explorer):
::    run_local.bat            -> preview mode  (build React + Flask)
::    run_local.bat dev        -> dev mode      (Flask + Vite hot-reload)
::    run_local.bat flask      -> Flask only    (reuse existing build)
::    run_local.bat install    -> install deps only
::
:: ══════════════════════════════════════════════════════════════════

:: Change to the folder where this .bat lives (handles double-click)
cd /d "%~dp0"

:: Pass any argument through to the PowerShell script
:: If called with no argument, PowerShell param default ("preview") applies
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" %1

:: Keep the window open so you can read errors if it exits unexpectedly
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [local] Script exited with error code %ERRORLEVEL%
    echo [local] Press any key to close this window.
    pause >nul
)
