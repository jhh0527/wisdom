# -*- coding: utf-8 -*-
"""wisdom 워크스페이스(열린 폴더) 기준 기본 경로."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIRNAME = "4_2pngFileName"


def _ensure_wisdom_on_path(from_file: str | Path) -> None:
    for base in [Path.cwd(), *Path(from_file).resolve().parents]:
        if (base / "wisdom_root.py").is_file():
            s = str(base)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise ImportError("wisdom_root.py not found — wisdom 폴더를 워크스페이스 루트로 여세요.")


_ensure_wisdom_on_path(__file__)
from wisdom_root import module_dir, module_output, resolve_wisdom_root
from wisdom_workspace import get_workspace_dir, resolve_module_output


def _project_root() -> Path:
    found = module_dir(PROJECT_DIRNAME)
    if found.is_dir():
        return found
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p
    return start


def _wisdom_root() -> Path:
    return resolve_wisdom_root()


def default_srt_file() -> Path:
    ws = get_workspace_dir()
    if ws is not None:
        cand = ws / "3_ttsToVoice" / "output" / "all.srt"
        if cand.is_file():
            return cand
    return resolve_module_output("3_ttsToVoice") / "all.srt"


def default_png_dir() -> Path:
    """기본 PNG 폴더: ``4_1pngToJpg/input`` (작업 폴더 우선)."""
    ws = get_workspace_dir()
    if ws is not None:
        return (ws / "4_1pngToJpg" / "input").resolve()
    return (module_dir("4_1pngToJpg") / "input").resolve()


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
