@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Kupido Player 4.5 - Build Pipeline
echo ============================================================

cd /d "%~dp0"

:: 1. Build Standalone PyInstaller Executable
echo [1/3] Building Standalone No-Console Executable (Kupido.exe)...
"venv\Scripts\pyinstaller.exe" --noconsole --onefile --name "Kupido" --icon="kupido.ico" --add-data="assets;assets" --add-data="kupido.ico;." kupido_player.py

if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] PyInstaller build failed or partial. Continuing with source distribution...
) else (
    echo [OK] Kupido.exe successfully generated in dist\
)

:: 2. Compile Inno Setup Installer
echo [2/3] Compiling Inno Setup 6 Installer...
set "ISCC=C:\Users\%USERNAME%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if not exist "%ISCC%" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if exist "%ISCC%" (
    "%ISCC%" "..\..\installer\setup.iss"
    echo [OK] Installer generated at installer\output\Kupido_Player_4.5_Setup.exe
) else (
    echo [INFO] Inno Setup ISCC.exe not found on default paths. Please run setup.iss manually.
)

echo [3/3] Build completed!
pause
