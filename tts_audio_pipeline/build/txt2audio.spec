# -*- mode: python ; coding: utf-8 -*-
"""Windows 단일 실행 파일(onefile) 빌드용 PyInstaller 스펙."""

import os

from PyInstaller.utils.hooks import collect_submodules

specdir = os.path.dirname(os.path.abspath(SPEC))
proot = os.path.normpath(os.path.join(specdir, ".."))

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
]

a = Analysis(
    [os.path.join(proot, "run_txt2audio.py")],
    pathex=[proot],
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
    name="txt2audio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
