@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "CLAW_HOME=%~dp0"
cd /d "%CLAW_HOME%"

set "PYTHON="

rem 1) project venv
if exist "%CLAW_HOME%.venv\Scripts\python.exe" (
    set "PYTHON=%CLAW_HOME%.venv\Scripts\python.exe"
)

rem 2) scan common Python install paths
if "!PYTHON!"=="" (
    for %%p in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
    ) do (
        if exist %%p set "PYTHON=%%p"
    )
)

rem 3) fallback
if "!PYTHON!"=="" set "PYTHON=python3"

echo ========================================
echo   py-tiny-claw  Interactive CLI
echo   Python: !PYTHON!
echo ========================================
echo.

"!PYTHON!" "%CLAW_HOME%main.py" %*

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] Exit code: !ERRORLEVEL!
    pause >nul
)
