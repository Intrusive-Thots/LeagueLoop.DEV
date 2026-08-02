
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "Development Launcher.lnk"

$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "C:\Users\Malcolm\LeagueLoop.DEV\launch_dev.bat"
$sc.WorkingDirectory = "C:\Users\Malcolm\LeagueLoop.DEV"
$sc.IconLocation = "C:\Users\Malcolm\LeagueLoop.DEV\assets\queqq_dev.ico,0"
$sc.Description = "Queqq Development Mode"
$sc.Save()

Write-Host "Updated Shortcut at $shortcutPath"
Write-Host "  Target: $sc.TargetPath"
Write-Host "  Icon: $sc.IconLocation"
