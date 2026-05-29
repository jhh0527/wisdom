# -*- mode: python ; coding: utf-8 -*-
"""Wisdom Hub — 탭으로 하위 프로그램 실행 (콘솔 없음)."""

import os

specdir = os.path.dirname(os.path.abspath(SPEC))
hub_py = os.path.normpath(os.path.join(specdir, "..", "wisdom_hub.py"))

hiddenimports = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.font",
]

a = Analysis(
    [hub_py],
    pathex=[os.path.dirname(hub_py)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    name="WisdomHub",
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
