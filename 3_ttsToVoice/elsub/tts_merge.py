# -*- coding: utf-8 -*-
"""TTS 줄 병합: 문장부호로 끝나지 않으면 다음 줄과 한 번에 합성."""

from __future__ import annotations

from elsub.elevenlabs_client import strip_tts_tags
from elsub.parser import CaptionLine

# 마침표·쉼표·느낌표·물음표·콜론·세미콜론(ASCII·전각·일부 CJK)
_PAUSE_END_CHARS = frozenset(
    ".,!?;:。"
    "．，、！？：；"
)


def tts_ends_with_pause_punctuation(tts: str) -> bool:
    """태그 제거 후 끝 문자가 쉼/끊김용 문장부호이면 True."""
    plain = strip_tts_tags(tts).strip()
    if not plain:
        return True
    return plain[-1] in _PAUSE_END_CHARS


def group_entries_for_synthesis(entries: list[CaptionLine]) -> list[list[CaptionLine]]:
    """이전 줄 TTS가 문장부호로 끝나지 않으면 다음 줄과 같은 합성 묶음."""
    if not entries:
        return []
    groups: list[list[CaptionLine]] = [[entries[0]]]
    for e in entries[1:]:
        if tts_ends_with_pause_punctuation(groups[-1][-1].tts):
            groups.append([e])
        else:
            groups[-1].append(e)
    return groups


def merge_group_tts(group: list[CaptionLine]) -> str:
    """한 묶음의 TTS 문자열을 이어 붙입니다(자막 줄바꿈·공백 없이)."""
    return "".join(e.tts for e in group)


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
