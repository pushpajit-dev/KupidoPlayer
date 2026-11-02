@echo off
setlocal enabledelayedexpansion

title Kupido Player 4.5 Launcher

:: Check for bundled / local venv pythonw
if exist "%~dp0venv\Scripts\pythonw.exe" (
    start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0kupido_player.py"
    exit /b 0
)

if exist "%~dp0..\venv\Scripts\pythonw.exe" (
    start "" "%~dp0..\venv\Scripts\pythonw.exe" "%~dp0kupido_player.py"
    exit /b 0
)

:: Check if Python is installed on system PATH
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%~dp0kupido_player.py"
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not found on PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: If dependencies missing, install them
echo [INFO] First-time setup: Checking required dependencies...
python -m pip install -r "%~dp0requirements.txt" --quiet

:: Launch smoothly with pythonw (no terminal)
start "" pythonw "%~dp0kupido_player.py"
exit /b 0
