; LeagueLoop Installer — Inno Setup Script

#define AppVersion "2-09-261-0317"
#define VersionInfoVersion "2.9.261.317"

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
SetupIconFile=assets\icon-f871f4e9.ico
UninstallDisplayIcon={app}\app.ico
Compression=lzma2/ultra64
SolidCompression=yes
LZMADictionarySize=65536
LZMAUseSeparateProcess=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove stale runtime-generated files from previous installs that cause PermissionError
Type: files; Name: "{app}\debug.log"
Type: files; Name: "{app}\error.log"
Type: files; Name: "{app}\debug.log.*"
Type: files; Name: "{app}\error.log.*"

[Files]
Source: "dist\LeagueLoop\LeagueLoop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\LeagueLoop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon-f871f4e9.ico"; DestDir: "{app}"; DestName: "app.ico"; Flags: ignoreversion
Source: "assets\icon-f871f4e9.ico"; DestDir: "{app}\assets"; DestName: "icon-f871f4e9.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\LeagueLoop"; Filename: "{app}\LeagueLoop.exe"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\LeagueLoop"; Filename: "{app}\LeagueLoop.exe"; Tasks: desktopicon; IconFilename: "{app}\app.ico"

[Run]
Filename: "{app}\LeagueLoop.exe"; Description: "{cm:LaunchProgram,LeagueLoop}"; Flags: nowait postinstall skipifsilent
