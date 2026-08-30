# -*- coding: utf-8 -*-
"""부 줄거리 파일에서 마스터 줄기·말미 장 발췌."""

from __future__ import annotations

import re
from pathlib import Path

_CHAPTER_H = re.compile(r"^##\s*제\s*(\d+)\s*장", re.M)
_STEM_FENCE = re.compile(
    r"##\s*마스터\s*줄기[^\n]*\n+(?:```[^\n]*\n)?(.*?)(?:```|\n##\s)",
    re.S | re.I,
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except OSError:
        return ""


def extract_master_stem(text: str, *, max_chars: int = 1200) -> str:
    if not text:
        return ""
    m = _STEM_FENCE.search(text)
    if m:
        body = m.group(1).strip()
        if body:
            return body[:max_chars]
    # fallback: 상단 요약 블록
    lines = text.splitlines()
    buf: list[str] = []
    for line in lines[:40]:
        if _CHAPTER_H.match(line):
            break
        buf.append(line)
    out = "\n".join(buf).strip()
    return out[:max_chars] if out else text[:max_chars].strip()


def split_chapter_sections(text: str) -> list[tuple[int, str]]:
    """[(장번호, 절 본문 incl. 헤더), ...] 장 번호 오름차순."""
    matches = list(_CHAPTER_H.finditer(text or ""))
    if not matches:
        return []
    out: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        ch = int(m.group(1))
        out.append((ch, text[start:end].strip()))
    out.sort(key=lambda x: x[0])
    return out


def last_chapter_excerpts(text: str, *, n: int = 2, max_chars: int = 4500) -> str:
    secs = split_chapter_sections(text)
    if not secs:
        return (text or "")[-max_chars:].strip()
    take = secs[-max(1, n) :]
    body = "\n\n".join(s for _, s in take).strip()
    if len(body) > max_chars:
        return body[-max_chars:]
    return body


def compress_volume_summary(text: str, *, max_chars: int = 800) -> str:
    stem = extract_master_stem(text, max_chars=max_chars)
    if stem:
        return stem[:max_chars]
    return (text or "")[:max_chars].strip()


def bible_excerpt(path: Path, *, max_chars: int = 3500) -> str:
    if not path.is_file():
        return ""
    body = read_text(path).strip()
    if len(body) > max_chars:
        return body[:max_chars] + "\n…(이하 생략)…"
    return body
