# -*- coding: utf-8 -*-
"""``md/image.md.txt`` 이미지 생성 지침."""

from __future__ import annotations

import sys
from pathlib import Path

_GUIDE_NAME = "image.md.txt"


def guide_path() -> Path:
    from wisdom_root import module_dir

    return module_dir("2_2_srtToImage") / "md" / _GUIDE_NAME


def load_image_guide() -> str:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass) / "md" / _GUIDE_NAME)
    candidates.append(guide_path())
    candidates.append(Path(__file__).resolve().parents[1] / "md" / _GUIDE_NAME)
    for p in candidates:
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return ""
