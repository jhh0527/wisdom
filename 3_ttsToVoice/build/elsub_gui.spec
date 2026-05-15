# -*- mode: python ; coding: utf-8 -*-
"""3_ttsToVoice GUI 빌드 스펙 (콘솔 없음)."""

import os

from PyInstaller.utils.hooks import collect_submodules

specdir = os.path.dirname(os.path.abspath(SPEC))
proot = os.path.normpath(os.path.join(specdir, ".."))

_example = os.path.join(proot, "elsub_config.example.json")
datas = [(_example, ".")] if os.path.isfile(_example) else []

hidden = collect_submodules("elsub")
hidden += [
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.font",
    "tkinter.scrolledtext",
]

a = Analysis(
    [os.path.join(proot, "run_elsub_gui.py")],
    pathex=[proot],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="3_ttsToVoice_gui",
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
