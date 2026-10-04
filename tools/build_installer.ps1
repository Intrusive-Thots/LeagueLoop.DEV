# Clean build of LeagueLoop installer. Writes build_done.txt with exit codes.
Set-Location (Split-Path $PSScriptRoot -Parent)
Remove-Item build_done.txt -ErrorAction SilentlyContinue
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist\LeagueLoop) { Remove-Item -Recurse -Force dist\LeagueLoop }
if (Test-Path dist\LeagueLoop_Installer.exe) { Remove-Item -Force dist\LeagueLoop_Installer.exe }
& .venv\Scripts\pyinstaller.exe --clean -y LeagueLoop.spec *> build_pyi.log
$pyi = $LASTEXITCODE
"PYI=$pyi" | Out-File build_done.txt
if ($pyi -eq 0) {
    & C:\InnoSetup\ISCC.exe installer.iss *> build_iss.log
    "ISCC=$LASTEXITCODE" | Out-File -Append build_done.txt
}
"DONE" | Out-File -Append build_done.txt
