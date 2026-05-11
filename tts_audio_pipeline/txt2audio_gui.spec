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
    # chatterbox.py — 모듈 로드 시 HF Hub용 httpx 훅 (함수 내부 import라 정적 분석 누락됨)
    "httpx",
    "httpcore",
    "h11",
    "huggingface_hub",
    "huggingface_hub.utils",
    "huggingface_hub.utils._http",
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
