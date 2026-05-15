# -*- mode: python ; coding: utf-8 -*-
"""Video Studio 단일 exe (Tkinter + FFmpeg 호출만 포함; FFmpeg 자체는 별도 설치)."""

import os

from PyInstaller.utils.hooks import collect_submodules

specdir = os.path.dirname(os.path.abspath(SPEC))
proot = os.path.normpath(os.path.join(specdir, ".."))

hidden = collect_submodules("videostudio")

a = Analysis(
    [os.path.join(proot, "run_gui.py")],
    pathex=[proot],
    binaries=[],
    datas=[],
    hiddenimports=hidden
    + [
        "tkinter",
        "tkinter.ttk",
        "tkinter.font",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.scrolledtext",
    ],
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
    name="VideoStudio",
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
