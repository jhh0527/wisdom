# -*- coding: utf-8 -*-
"""``SRT_XXX.png`` 출력 파일명."""

from __future__ import annotations


def srt_png_name(number: int, *, pad: int = 3) -> str:
    if number < 0:
        raise ValueError(f"SRT 번호는 0 이상이어야 합니다: {number}")
    return f"SRT_{number:0{pad}d}.png"
