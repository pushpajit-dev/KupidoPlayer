; =====================================================================
; Kupido Player 4.5 - Nullsoft Scriptable Install System (NSIS) Script
; =====================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "Kupido Player 4.5"
OutFile "output\Kupido_Player_4.5_NSIS_Setup.exe"
InstallDir "$PROGRAMFILES64\Kupido Player"
InstallDirRegKey HKCU "Software\KupidoPlayer" "Install_Dir"
RequestExecutionLevel admin

; UI Configuration
!define MUI_ICON "kupido.ico"
!define MUI_UNICON "kupido.ico"
!define MUI_ABORTWARNING

; Installer Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Finish Page with Silent Launch option
!define MUI_FINISHPAGE_RUN "$SYSDIR\wscript.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS '"$INSTDIR\run_kupido_silent.vbs"'
!define MUI_FINISHPAGE_RUN_TEXT "Launch Kupido Player 4.5"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Version Information
VIProductVersion "4.5.0.0"
VIAddVersionKey "ProductName" "Kupido Player"
VIAddVersionKey "CompanyName" "Kupido Media Lab"
VIAddVersionKey "LegalCopyright" "(c) 2026 Kupido Media Lab"
VIAddVersionKey "FileDescription" "Kupido Player Setup"
VIAddVersionKey "FileVersion" "4.5.0.0"

Section "Kupido Player (Required)" SecCore
    SetOutPath "$INSTDIR"

    ; Core application files
    File /nonfatal "..\development\source\4.5\dist\Kupido.exe"
    File "..\development\source\4.5\kupido_player.py"
    File "..\development\source\4.5\LICENSE.txt"
    File "..\development\source\4.5\requirements.txt"
    File "..\development\source\4.5\kupido.ico"
    File "..\development\source\4.5\run_kupido_silent.vbs"
    File "..\development\source\4.5\launch_kupido.bat"

    ; Assets and Icons
    SetOutPath "$INSTDIR\assets"
    File /r "..\development\source\4.5\assets\*.*"

    SetOutPath "$INSTDIR"

    ; Silent python dependency installer if standalone binary is not bundled
    IfFileExists "$INSTDIR\Kupido.exe" skip_deps
        nsExec::Exec 'cmd.exe /C python -m pip install -r "$INSTDIR\requirements.txt" --quiet'
    skip_deps:

    ; Registry keys
    WriteRegStr HKCU "Software\KupidoPlayer" "Install_Dir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer" "DisplayName" "Kupido Player 4.5"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer" "DisplayIcon" "$INSTDIR\kupido.ico"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer" "Publisher" "Kupido Media Lab"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer" "DisplayVersion" "4.5"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Start Menu Shortcuts
    CreateDirectory "$SMPROGRAMS\Kupido Player"
    CreateShortcut "$SMPROGRAMS\Kupido Player\Kupido Player.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\run_kupido_silent.vbs"' "$INSTDIR\kupido.ico"
    CreateShortcut "$SMPROGRAMS\Kupido Player\Kupido Player (Console Diagnostics).lnk" "$INSTDIR\launch_kupido.bat" "" "$INSTDIR\kupido.ico"
    CreateShortcut "$SMPROGRAMS\Kupido Player\Uninstall Kupido Player.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe"

    ; Desktop Shortcut
    CreateShortcut "$DESKTOP\Kupido Player.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\run_kupido_silent.vbs"' "$INSTDIR\kupido.ico"
SectionEnd

Section "Uninstall"
    Delete "$DESKTOP\Kupido Player.lnk"
    RMDir /r "$SMPROGRAMS\Kupido Player"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\KupidoPlayer"
    DeleteRegKey HKCU "Software\KupidoPlayer"

    RMDir /r "$INSTDIR\assets"
    RMDir /r "$INSTDIR\temp"
    RMDir /r "$INSTDIR\cache"
    Delete "$INSTDIR\*.*"
    RMDir "$INSTDIR"
SectionEnd
