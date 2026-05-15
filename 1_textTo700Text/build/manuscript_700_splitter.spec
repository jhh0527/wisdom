# -*- mode: python ; coding: utf-8 -*-
"""대본 700자 분할 GUI (콘솔 없음, 단일 exe)."""

import os

specdir = os.path.dirname(os.path.abspath(SPEC))
app_py = os.path.normpath(os.path.join(specdir, "..", "manuscript_700_splitter.py"))

hiddenimports = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.font",
]

a = Analysis(
    [app_py],
    pathex=[os.path.dirname(app_py)],
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
    name="manuscript_700_splitter",
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
