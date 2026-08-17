# Recreate the LeagueLoop desktop shortcuts using the native Windows API.
#
# Only needed as a fallback: if the shortcuts written directly to the Desktop
# do not work, run this and Windows will build them itself via WScript.Shell.
#
#   Right-click -> Run with PowerShell
#   (or)  powershell -ExecutionPolicy Bypass -File tools\fix_desktop_shortcuts.ps1
#
# Background: the old "Development Launcher" shortcut pointed at
#   \\MYDESKTOP\Users\Administrator\LeagueLoop.DEV\launch_dev.bat
# — a UNC path to a different machine and user profile — so Windows tried the
# network location first and stalled or failed.

$ErrorActionPreference = "Stop"

$repo    = "C:\Users\Malcolm\LeagueLoop.DEV"
$desktop = [Environment]::GetFolderPath("Desktop")
$icon    = Join-Path $repo "assets\app.ico"
$shell   = New-Object -ComObject WScript.Shell

function New-LLShortcut {
    param($Name, $Target, $Description)

    if (-not (Test-Path $Target)) {
        Write-Warning "Target missing, skipping: $Target"
        return
    }

    $path = Join-Path $desktop $Name
    $sc = $shell.CreateShortcut($path)
    $sc.TargetPath       = $Target
    $sc.WorkingDirectory = $repo
    $sc.Description      = $Description
    if (Test-Path $icon) { $sc.IconLocation = $icon }
    $sc.Save()

    Write-Host "  OK  $Name" -ForegroundColor Green
    Write-Host "      -> $Target" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host " Rebuilding LeagueLoop desktop shortcuts" -ForegroundColor Cyan
Write-Host ""

New-LLShortcut -Name "Development Launcher.lnk" `
               -Target (Join-Path $repo "launch_dev.bat") `
               -Description "LeagueLoop Development Mode"

New-LLShortcut -Name "LeagueLoop Qt (DEV).lnk" `
               -Target (Join-Path $repo "launch_qt_dev.bat") `
               -Description "LeagueLoop - new PySide6 shell (migration build)"

Write-Host ""
Write-Host " Done." -ForegroundColor Cyan
Write-Host ""
