# -*- coding: utf-8 -*-
"""wisdom 저장소 기준 기본 입·출력 경로."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIRNAME = "4_1pngToJpg"
OUTPUT_DIRNAME = "output"


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p
    return start


def default_output_dir() -> Path:
    return _project_root() / OUTPUT_DIRNAME


def default_input_dir() -> Path:
    """기본 입력: ``4_srtToImage/output`` (PNG·old 등)."""
    root = _project_root()
    for p in root.parents:
        cand = p / "4_srtToImage" / "output"
        if cand.is_dir():
            return cand
    return root / "input"
