# -*- coding: utf-8 -*-
"""3_ttsToVoice: knowledgetts 형식 줄 파싱 (`1-1 원본: ... TTS: ...`).

`CaptionLine.part_id` 프로퍼티로 caption_id의 앞 숫자(파트 번호)를 얻습니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PART_HEADER = re.compile(r"^\s*\d+\.\{\}\s*$")
SUMMARY = re.compile(r"^\s*\*\*요약")


@dataclass(frozen=True)
class CaptionLine:
    caption_id: str
    original: str
    tts: str

    @property
    def part_id(self) -> str:
        """caption_id가 "1-1" 형태일 때 앞 숫자(파트 번호)를 반환합니다."""
        return self.caption_id.split("-", 1)[0]


def parse_knowledgetts_block(text: str) -> list[CaptionLine]:
    out: list[CaptionLine] = []
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if PART_HEADER.match(line) or SUMMARY.match(line):
            continue
        m = re.match(r"^\s*(\d+-\d+)\s+원본:\s*(.+)$", line)
        if not m:
            continue
        rest = m.group(2)
        sep = " TTS: "
        if sep not in rest:
            continue
        orig, tts = rest.split(sep, 1)
        out.append(CaptionLine(m.group(1), orig.strip(), tts.strip()))
    return out
