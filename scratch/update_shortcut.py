import os
import subprocess

ico_abs = os.path.abspath("assets/queqq_dev.ico")
bat_abs = os.path.abspath("launch_dev.bat")
work_dir = os.path.abspath(".")

ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "Development Launcher.lnk"

$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "{bat_abs}"
$sc.WorkingDirectory = "{work_dir}"
$sc.IconLocation = "{ico_abs},0"
$sc.Description = "Queqq Development Mode"
$sc.Save()

Write-Host "Updated Shortcut at $shortcutPath"
Write-Host "  Target: $sc.TargetPath"
Write-Host "  Icon: $sc.IconLocation"
"""

with open("scratch/update_sc.ps1", "w", encoding="utf-8") as f:
    f.write(ps_script)

res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "scratch/update_sc.ps1"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
