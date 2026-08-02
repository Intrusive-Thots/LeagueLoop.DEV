import os
import subprocess

ps_script = """
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('C:\\Users\\Malcolm\\Desktop\\Development Launcher.lnk')
Write-Host "Target:" $sc.TargetPath
Write-Host "Arguments:" $sc.Arguments
Write-Host "WorkingDir:" $sc.WorkingDirectory
Write-Host "Icon:" $sc.IconLocation
"""

with open("scratch/inspect.ps1", "w", encoding="utf-8") as f:
    f.write(ps_script)

res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scratch/inspect.ps1"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
