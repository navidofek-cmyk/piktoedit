# -*- mode: python ; coding: utf-8 -*-
# Sestaveni samostatneho .exe: python -m PyInstaller --noconfirm --clean PiktoEdit.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Sablony jedou uvnitr .exe a pri prvnim spusteni se rozbali vedle nej.
    datas=[('sablony', 'sablony')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Do piktogramu nepotrebujeme sit, databaze ani web engine.
    excludes=[
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQml', 'PySide6.Qt3DCore',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtBluetooth', 'PySide6.QtNetworkAuth',
        'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
        'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtDesigner', 'PySide6.QtHelp',
        'tkinter', 'unittest', 'pydoc_data', 'numpy', 'matplotlib',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PiktoEdit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
