# -*- coding: utf-8 -*-
"""TTS 줄 병합: 문장부호·호흡 태그로 끊고, 이어 읽을 줄만 한 API 호출로 합성."""

from __future__ import annotations

import re

from elsub.elevenlabs_client import SUBTITLE_LINE_BREAK, strip_tts_tags
from elsub.parser import CaptionLine

# 마침표·쉼표·느낌표·물음표·콜론·세미콜론·말줄임(ASCII·전각·일부 CJK)
_PAUSE_END_CHARS = frozenset(
    ".,!?;:…"
    "．，、！？：；"
    "」』\"')】〉"
)

_LEADING_PAUSE_TAG_RE = re.compile(
    r"^\s*\[(?:short pause|breathes)(?:\]\s*\[(?:breathes|continues))*\]",
    re.IGNORECASE,
)
_TRAILING_PAUSE_TAG_RE = re.compile(r"\[(?:short pause|breathes)\]\s*$", re.IGNORECASE)


def tts_has_leading_pause_marker(tts: str) -> bool:
    """TTS 앞에 ``[short pause]``·``[breathes]`` 계열이 있으면 True."""
    return bool(_LEADING_PAUSE_TAG_RE.match(tts.strip()))


def tts_has_trailing_pause_marker(tts: str) -> bool:
    """TTS 끝에 ``[breathes]``·``[short pause]`` 가 있으면 True."""
    return bool(_TRAILING_PAUSE_TAG_RE.search(tts.strip()))


def tts_ends_with_pause_punctuation(tts: str) -> bool:
    """태그 제거 후 끝 문자가 쉼/끊김용 문장부호이면 True."""
    if tts_has_trailing_pause_marker(tts):
        return True
    plain = strip_tts_tags(tts).strip()
    if not plain:
        return True
    return plain[-1] in _PAUSE_END_CHARS


def group_entries_for_synthesis(entries: list[CaptionLine]) -> list[list[CaptionLine]]:
    """이전 줄이 끊김 지점이면 다음 줄을 새 합성 묶음으로 시작합니다."""
    if not entries:
        return []
    groups: list[list[CaptionLine]] = [[entries[0]]]
    for e in entries[1:]:
        if tts_has_leading_pause_marker(e.tts):
            groups.append([e])
        elif tts_ends_with_pause_punctuation(groups[-1][-1].tts):
            groups.append([e])
        else:
            groups[-1].append(e)
    return groups


def merge_group_tts(group: list[CaptionLine]) -> str:
    """한 묶음 TTS. 앞 줄이 문장부호·호흡 태그로 끝나지 않으면 짧은 ``<break>`` 로 띄어 읽습니다."""
    if not group:
        return ""
    if len(group) == 1:
        return group[0].tts
    parts: list[str] = [group[0].tts]
    for prev, curr in zip(group, group[1:]):
        if not tts_ends_with_pause_punctuation(prev.tts):
            parts.append(SUBTITLE_LINE_BREAK)
        parts.append(curr.tts)
    return "".join(parts)


def split_duration_ms(total_ms: int, weights: list[int], *, min_ms: int = 1) -> list[int]:
    """묶음 MP3 길이를 줄별 가중치(예: 글자 수)로 나눕니다."""
    if not weights:
        return []
    if len(weights) == 1:
        return [max(min_ms, int(total_ms))]
    w = [max(1, int(x)) for x in weights]
    s = sum(w)
    scaled = [max(min_ms, int(round(total_ms * x / s))) for x in w]
    drift = int(total_ms) - sum(scaled)
    scaled[-1] = max(min_ms, scaled[-1] + drift)
    return scaled
