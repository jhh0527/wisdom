# -*- mode: python ; coding: utf-8 -*-
"""창 전용 GUI 실행 파일 (콘솔 없음)."""

import os

from PyInstaller.utils.hooks import collect_submodules

specdir = os.path.dirname(os.path.abspath(SPEC))

hidden = collect_submodules("txt2audio")
hidden += [
    "edge_tts",
    "certifi",
    "aiohttp",
    "multidict",
    "yarl",
    "frozenlist",
    "aiosignal",
    "attrs",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.font",
]

a = Analysis(
    [os.path.join(specdir, "run_txt2audio_gui.py")],
    pathex=[specdir],
    binaries=[],
    datas=[],
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
    name="txt2audio_gui",
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
