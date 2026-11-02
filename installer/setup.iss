; =====================================================================
; Kupido Player 4.5 - Professional Inno Setup 6 Installer Script
; =====================================================================

#define MyAppName "Kupido Player"
#define MyAppVersion "4.5"
#define MyAppPublisher "Kupido Media Lab"
#define MyAppURL "https://github.com/kupido-player"
#define MyAppSupportURL "https://github.com/kupido-player/support"
#define MyAppUpdatesURL "https://github.com/kupido-player/releases"
#define MyAppExeName "Kupido.exe"
#define MyLauncherVbs "run_kupido_silent.vbs"

[Setup]
; Basic Application Identification
AppId={{C8E19B14-5A58-4D4F-8813-A3B7E9F41984}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppUpdatesURL}

; Directory Selection with Browser
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
AllowNoIcons=yes

; Agreement / License Page
LicenseFile=LICENSE.txt

; Branding & Visuals
SetupIconFile=kupido.ico
UninstallDisplayIcon={app}\kupido.ico
WizardStyle=modern

; Compression Settings
Compression=lzma2/ultra64
SolidCompression=yes

; Output Configuration
OutputDir=output
OutputBaseFilename=Kupido_Player_4.5_Setup
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Standalone executable if built
Source: "..\development\source\4.5\dist\Kupido.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; Core Source Files
Source: "..\development\source\4.5\kupido_player.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\development\source\4.5\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\development\source\4.5\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\development\source\4.5\kupido.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\development\source\4.5\run_kupido_silent.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\development\source\4.5\launch_kupido.bat"; DestDir: "{app}"; Flags: ignoreversion
; Assets and Icons
Source: "..\development\source\4.5\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu Shortcuts
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyLauncherVbs}"; IconFilename: "{app}\kupido.ico"; Comment: "Launch Kupido Player 4.5"
Name: "{autoprograms}\{#MyAppName}\Kupido Player (Console Mode)"; Filename: "{app}\launch_kupido.bat"; IconFilename: "{app}\kupido.ico"; Comment: "Launch Kupido Player with diagnostics console"
Name: "{autoprograms}\{#MyAppName}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\kupido.ico"
; Desktop Shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyLauncherVbs}"; IconFilename: "{app}\kupido.ico"; Tasks: desktopicon; Comment: "Launch Kupido Player 4.5"

[Run]
; Launch Application cleanly with NO console window (zero terminal flash)
Filename: "wscript.exe"; Parameters: """{app}\{#MyLauncherVbs}"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PythonPath: String;
  PythonFound: Boolean;

// Check if Python 3 is installed in Registry or System PATH
function CheckPythonInstalled(): Boolean;
var
  RegPath: String;
  Versions: TArrayOfString;
  I: Integer;
begin
  Result := False;
  PythonPath := '';

  // 1. Check Current User Registry
  if RegGetSubkeyNames(HKCU, 'Software\Python\PythonCore', Versions) then
  begin
    for I := 0 to GetArrayLength(Versions) - 1 do
    begin
      RegPath := 'Software\Python\PythonCore\' + Versions[I] + '\InstallPath';
      if RegQueryStringValue(HKCU, RegPath, 'ExecutablePath', PythonPath) then
      begin
        if FileExists(PythonPath) then
        begin
          Result := True;
          Exit;
        end;
      end;
    end;
  end;

  // 2. Check Local Machine Registry
  if RegGetSubkeyNames(HKLM, 'Software\Python\PythonCore', Versions) then
  begin
    for I := 0 to GetArrayLength(Versions) - 1 do
    begin
      RegPath := 'Software\Python\PythonCore\' + Versions[I] + '\InstallPath';
      if RegQueryStringValue(HKLM, RegPath, 'ExecutablePath', PythonPath) then
      begin
        if FileExists(PythonPath) then
        begin
          Result := True;
          Exit;
        end;
      end;
    end;
  end;

  // 3. Check System PATH via python.exe
  if FileExists(ExpandConstant('{cmd}')) then
  begin
    Result := True;
  end;
end;

// Pre-install check for Python environment
function InitializeSetup(): Boolean;
begin
  PythonFound := CheckPythonInstalled();
  Result := True;
end;

// Post-install module verification and silent dependency setup
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  ReqPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    ReqPath := ExpandConstant('{app}\requirements.txt');
    // If standalone exe does not exist, run background pip install silently with SW_HIDE
    if not FileExists(ExpandConstant('{app}\Kupido.exe')) and FileExists(ReqPath) then
    begin
      // Execute silent pip module install without terminal window
      Exec('cmd.exe', '/C python -m pip install -r "' + ReqPath + '" --quiet', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;
