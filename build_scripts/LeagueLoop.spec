# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import customtkinter
import os

ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter'),
        ('assets', 'assets'),
        ('config', 'config'),
        ('src/ui/theme/design_tokens.json', 'ui/theme'),
        ('src/ui/theme/design_tokens.json', 'src/ui/theme'),
        ('src/ui/theme/design_tokens.json', '.')
    ],
    hiddenimports=[
        'requests',
        'psutil',
        'PIL',
        'urllib3',
        'keyboard',
        'logging.handlers',
        'bs4',
        'winreg',
        'tkinter',
        *collect_submodules('tkinter'),
        'tkinterdnd2',
        'customtkinter',
        'packaging',
        'darkdetect',
        'pystray',
        'pypresence',
        'websockets',
        'lcu_driver',
        'aiohttp',
        'yarl',
        'multidict',
        'win32crypt'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ONEDIR build — produces dist/LeagueLoop/ folder for Inno Setup packaging
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LeagueLoop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon-f871f4e9.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LeagueLoop',
)
