# -*- coding: utf-8 -*-
"""Genspark SRT 후처리 — 장 제목 잔여만 다음 큐로 이동."""

from __future__ import annotations

import re

from srt_edit.script_io import detect_chapter_title, strip_elevenlabs_tags
from srt_edit.srt_diff import SrtCue, parse_srt_cues

# 「제N장. 부제.」또는 「제 N장, 부제.」— 부제 끝 마침표까지 제목, 이후 잔여
_CHAPTER_TITLE_CUT_RE = re.compile(
    r"^(제?\s*\d+\s*장[.,]\s*[^\n.]+)\.\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_CHAPTER_HEAD_RE = re.compile(r"^제?\s*\d+\s*장\b", re.IGNORECASE)


def _nospace(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def split_chapter_title_remainder(
    cue_text: str, chapter_title: str = ""
) -> tuple[str, str]:
    """첫 큐에서 장 제목(부제 마침표까지)과 잔여 본문을 분리.

    큐 문구·띄어쓰기는 그대로 두고 자르기만 한다.
    예: ``제16장. 배신자의 얼굴. 화산으로``
    → (``제16장. 배신자의 얼굴``, ``화산으로``)
    """
    raw = strip_elevenlabs_tags((cue_text or "").strip())
    if not raw:
        return "", ""
    m = _CHAPTER_TITLE_CUT_RE.match(raw)
    if m:
        title = (m.group(1) or "").strip()
        rest = re.sub(r"^[,.\s]+", "", (m.group(2) or "").strip()).strip()
        return title, rest

    # 대본 제목 길이(공백 무시)만큼 앞에서 절단 후 잔여
    title_ref = strip_elevenlabs_tags((chapter_title or "").strip())
    title_ns = _nospace(title_ref)
    if not title_ns:
        return raw, ""
    acc = 0
    cut = -1
    for i, ch in enumerate(raw):
        if ch.isspace():
            continue
        acc += 1
        if acc >= len(title_ns):
            cut = i + 1
            break
    if cut < 0:
        return raw, ""
    j = cut
    while j < len(raw) and raw[j].isspace():
        j += 1
    if j < len(raw) and raw[j] == ".":
        j += 1
    title = raw[:cut].strip()
    if j > cut and raw[j - 1] == ".":
        title = raw[: j - 1].strip()
    rest = re.sub(r"^[,.\s]+", "", raw[j:].strip()).strip()
    return title, rest


def apply_chapter_title_line_split(
    srt_text: str, script_text: str = ""
) -> tuple[str, int]:
    """Genspark(또는 STT) SRT 본문은 유지하고, 첫 큐 제목 잔여만 다음 큐로 옮김.

    Returns:
        (SRT 전체, 변경 여부 0/1)
    """
    cues = parse_srt_cues(srt_text)
    if not cues:
        body = srt_text if (not srt_text or srt_text.endswith("\n")) else srt_text + "\n"
        return body, 0

    script_lines = [
        strip_elevenlabs_tags(ln.strip())
        for ln in (script_text or "").splitlines()
        if ln.strip()
    ]
    chapter_title = detect_chapter_title(script_lines) or ""
    first = strip_elevenlabs_tags((cues[0].text or "").strip())
    if not _CHAPTER_HEAD_RE.match(first) and not chapter_title:
        body = srt_text if (not srt_text or srt_text.endswith("\n")) else srt_text + "\n"
        return body, 0

    title, rest = split_chapter_title_remainder(first, chapter_title)
    if not rest:
        body = srt_text if (not srt_text or srt_text.endswith("\n")) else srt_text + "\n"
        return body, 0

    new_cues: list[SrtCue] = [
        SrtCue(index=cues[0].index, timing=cues[0].timing, text=title)
    ]
    if len(cues) >= 2:
        nxt = strip_elevenlabs_tags((cues[1].text or "").strip())
        merged = f"{rest} {nxt}".strip() if nxt else rest
        new_cues.append(SrtCue(index=cues[1].index, timing=cues[1].timing, text=merged))
        new_cues.extend(cues[2:])
    else:
        new_cues.append(
            SrtCue(index=cues[0].index + 1, timing=cues[0].timing, text=rest)
        )

    blocks: list[str] = []
    for c in new_cues:
        text = strip_elevenlabs_tags(c.text)
        blocks.append(f"{c.index}\n{c.timing}\n{text}".rstrip() + "\n")
    body = "\n".join(blocks)
    if not body.endswith("\n"):
        body += "\n"
    return body, 1


def correct_srt_with_script(
    srt_text: str, script_text: str, *, min_ratio: float = 0.52
) -> tuple[str, int]:
    """Genspark 결과를 유지한 채 장 제목 잔여만 다음 줄로 보낸다."""
    del min_ratio
    return apply_chapter_title_line_split(srt_text, script_text)
