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
        ('config.json', '.')
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
        'tkinterdnd2',
        'customtkinter',
        'packaging',
        'darkdetect',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtQuickWidgets', 'PySide6.QtQuickControls2',
        'PySide6.QtBluetooth', 'PySide6.QtSensors', 'PySide6.QtScxml', 'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
    ],
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LeagueLoop',
)
