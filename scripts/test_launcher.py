import os, winreg

candidates = [
    r'C:\Riot Games\Riot Client\RiotClientServices.exe',
    r'D:\Riot Games\Riot Client\RiotClientServices.exe',
    r'E:\Riot Games\Riot Client\RiotClientServices.exe',
    r'C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe',
    os.path.join(os.environ.get('USERPROFILE', ''), r'Riot Games\Riot Client\RiotClientServices.exe')
]

for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
    try:
        key = winreg.OpenKey(hkey, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live')
        val, _ = winreg.QueryValueEx(key, 'UninstallString')
        if val and 'RiotClientServices.exe' in val:
            path = val.split('\"')[1] if '\"' in val else val.split(' ')[0]
            print(f'Registry found: {path}')
            if os.path.exists(path):
                candidates.insert(0, path)
    except Exception as e:
        print(f'Registry error for {hkey}: {e}')

found = []
for c in candidates:
    if os.path.exists(c):
        found.append(c)

print('Existing candidates:')
for f in found:
    print(f)
