; LeagueLoop Installer — Inno Setup Script

#define AppVersion "1-06-213-0805"
#define VersionInfoVersion "1.6.213.805"

[Setup]
AppName=LeagueLoop
AppVersion={#AppVersion}
VersionInfoVersion={#VersionInfoVersion}
AppPublisher=Malcolm
AppPublisherURL=https://github.com/Intrusive-Thots/LeagueLoop-Installer
AppSupportURL=https://github.com/Intrusive-Thots/LeagueLoop-Lock/issues
DefaultDirName={autopf}\LeagueLoop
DefaultGroupName=LeagueLoop
OutputDir=dist
OutputBaseFilename=LeagueLoop_Installer
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\LeagueLoop.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Remove stale runtime-generated files from previous installs that cause PermissionError
Type: files; Name: "{app}\debug.log"
Type: files; Name: "{app}\error.log"
Type: files; Name: "{app}\debug.log.*"
Type: files; Name: "{app}\error.log.*"

[Files]
Source: "dist\LeagueLoop\LeagueLoop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\LeagueLoop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LeagueLoop"; Filename: "{app}\LeagueLoop.exe"
Name: "{autodesktop}\LeagueLoop"; Filename: "{app}\LeagueLoop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LeagueLoop.exe"; Description: "{cm:LaunchProgram,LeagueLoop}"; Flags: nowait postinstall skipifsilent
