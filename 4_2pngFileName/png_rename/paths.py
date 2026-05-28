# -*- coding: utf-8 -*-
"""wisdom 저장소 기준 기본 경로."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIRNAME = "4_2pngFileName"


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        # dist/4_2pngFileName_gui.exe → 상위가 4_2pngFileName
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "dist" and exe_dir.parent.name == PROJECT_DIRNAME:
            return exe_dir.parent
        start = exe_dir
    else:
        start = Path(__file__).resolve().parent.parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p
    return start


def _wisdom_root() -> Path:
    root = _project_root()
    for p in [root, *root.parents]:
        if (p / "3_ttsToVoice").is_dir():
            return p
    return root.parent


def default_srt_file() -> Path:
    return _wisdom_root() / "3_ttsToVoice" / "output" / "all.srt"


def default_png_dir() -> Path:
    """기본 PNG 폴더: ``4_1pngToJpg/input``."""
    root = _wisdom_root()
    return (root / "4_1pngToJpg" / "input").resolve()


def resolve_initial_srt(
    cli: Path | None,
    saved: str | None,
) -> Path:
    fallback = default_srt_file()
    if cli is not None:
        p = cli.expanduser().resolve()
        if p.is_file():
            return p
    if saved:
        p = Path(saved).expanduser().resolve()
        if p.is_file():
            return p
    return fallback.resolve()


def resolve_initial_png_dir(
    cli: Path | None,
    saved: str | None,
) -> Path:
    """저장 경로가 없거나 유효하지 않으면 ``4_1pngToJpg/input``."""
    fallback = default_png_dir()
    if cli is not None:
        p = cli.expanduser().resolve()
        if p.is_dir():
            return p
    if saved:
        p = Path(saved).expanduser().resolve()
        if p.is_dir():
            return p
    return fallback
