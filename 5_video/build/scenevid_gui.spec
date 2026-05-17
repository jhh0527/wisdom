# -*- mode: python ; coding: utf-8 -*-
"""GUI 단일 실행 파일 (콘솔 없음)."""

import os

specdir = os.path.dirname(os.path.abspath(SPEC))
proot = os.path.normpath(os.path.join(specdir, ".."))

a = Analysis(
    [os.path.join(proot, "run_scenevid_gui.py")],
    pathex=[proot],
    binaries=[],
    datas=[],
    hiddenimports=[
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.font",
        "scenevid",
        "scenevid.cli",
        "scenevid.compose_render",
        "scenevid.compose_overrides",
        "scenevid.ffmpeg_render",
        "scenevid.subtitles",
        "scenevid.srt_parse",
        "scenevid.schema",
        "scenevid.script_parse",
        "scenevid.assets",
        "scenevid.media_paths",
        "scenevid.repo_paths",
        "scenevid.motion",
        "scenevid.srt_image_effects",
        "scenevid.gui_app",
        "scenevid.subprocess_util",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
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
    name="5_video_gui",
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
