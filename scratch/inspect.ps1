
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('C:\Users\Malcolm\Desktop\Development Launcher.lnk')
Write-Host "Target:" $sc.TargetPath
Write-Host "Arguments:" $sc.Arguments
Write-Host "WorkingDir:" $sc.WorkingDirectory
Write-Host "Icon:" $sc.IconLocation
