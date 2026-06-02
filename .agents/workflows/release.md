---
description: Full release pipeline — build executable, compile installer, publish to both repos
---
// turbo-all

# LeagueLoop Release Pipeline

Run this when the user says "release", "ship it", "publish", or "build and push".

## Steps

1. Clean previous build artifacts:
```powershell
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist\LeagueLoop) { Remove-Item -Recurse -Force dist\LeagueLoop }
```

2. Build the ONEDIR distribution with PyInstaller:
```powershell
.venv\Scripts\pyinstaller --clean LeagueLoop.spec 2>&1
```

3. Verify the executable was created:
```powershell
if (!(Test-Path "dist\LeagueLoop\LeagueLoop.exe")) { throw "BUILD FAILED: LeagueLoop.exe not found" }
[math]::Round((Get-Item "dist\LeagueLoop\LeagueLoop.exe").Length/1MB, 2)
```

4. Sign the executable:
```powershell
& "C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool\signtool.exe" sign /f "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\LeagueLoop_Cert.pfx" /p "LeagueLoop" /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\dist\LeagueLoop\LeagueLoop.exe"
```

5. Compile the Inno Setup installer:
```powershell
& "C:\InnoSetup\ISCC.exe" "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\installer.iss" 2>&1
```

6. Verify the installer was created:
```powershell
if (!(Test-Path "dist\LeagueLoop_Installer.exe")) { throw "INSTALLER FAILED: LeagueLoop_Installer.exe not found" }
Write-Output "Installer size: $([math]::Round((Get-Item 'dist\LeagueLoop_Installer.exe').Length/1MB, 2)) MB"
```

7. Sign the installer:
```powershell
& "C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool\signtool.exe" sign /f "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\LeagueLoop_Cert.pfx" /p "LeagueLoop" /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\dist\LeagueLoop_Installer.exe"
```

8. Push source code changes to the LeagueLoop-Lock repo:
```powershell
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop
git add -A
git commit -m "release: build $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin master
```

9. Copy the new installer to the Installer repo and push:
```powershell
Copy-Item "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\dist\LeagueLoop_Installer.exe" "C:\Users\Administrator\Desktop\LeagueLoop-Installer\LeagueLoop_Installer.exe" -Force
cd C:\Users\Administrator\Desktop\LeagueLoop-Installer
git add -A
git commit -m "release: update installer $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin master
```

10. Report final status:
```powershell
Write-Output "=== RELEASE COMPLETE ==="
Write-Output "Source:    https://github.com/Intrusive-Thots/LeagueLoop-Lock"
Write-Output "Installer: https://github.com/Intrusive-Thots/LeagueLoop-Installer"
```
