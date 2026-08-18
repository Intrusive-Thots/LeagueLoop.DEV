; LeagueLoop Installer — NSIS Script (Cross-Platform Alternative)
; Install location and metadata
!define APP_NAME "LeagueLoop"
!define APP_VERSION "1-08-135-0153"
!define APP_PUBLISHER "Malcolm"
!define APP_URL "https://github.com/Intrusive-Thots/LeagueLoop-Installer"

; Output file
OutFile "dist/LeagueLoop_Installer.exe"
Name "${APP_NAME}"
Caption "${APP_NAME} ${APP_VERSION} Setup"
BrandingText "${APP_NAME} ${APP_VERSION}"

; Default installation directory
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" ""

; Request admin privileges
RequestExecutionLevel admin

; Modern UI
!include "MUI2.nsh"
!define MUI_ICON "assets/app.ico"
!define MUI_UNICON "assets/app.ico"
; !define MUI_WELCOMEFINISHPAGE_BITMAP "assets\installer_background.bmp"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstall pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language
!insertmacro MUI_LANGUAGE "English"

; Installer section
Section "Install" SecInstall
    SetOutPath "$INSTDIR"
    
    ; Remove stale runtime-generated files from previous installs
    Delete "$INSTDIR\debug.log"
    Delete "$INSTDIR\error.log"
    Delete "$INSTDIR\debug.log.*"
    Delete "$INSTDIR\error.log.*"
    
    ; Copy all files from PyInstaller output
    File /r "dist\LeagueLoop\*.*"
    
    ; Create start menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_NAME}.exe"
    
    ; Create desktop shortcut
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_NAME}.exe"
    
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; Register uninstaller in Windows
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_NAME}.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "URLInfoAbout" "${APP_URL}"
SectionEnd

; Uninstaller section
Section "Uninstall"
    ; Remove shortcuts
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    
    ; Remove registry entries
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKLM "Software\${APP_NAME}"
    
    ; Remove installed files
    RMDir /r "$INSTDIR"
SectionEnd

; Auto-launch after installation
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_NAME}.exe"
!insertmacro MUI_PAGE_FINISH
