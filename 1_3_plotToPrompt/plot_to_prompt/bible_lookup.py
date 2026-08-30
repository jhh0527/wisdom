# -*- coding: utf-8 -*-
"""chapter_map · timeline 에서 장 메타 자동 채움."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from plot_to_prompt.brief_builder import expand_event_field, parse_chapter_map_row


@dataclass
class ChapterMeta:
    body_title: str = ""
    youtube_title: str = ""
    event_ids: list[str] = field(default_factory=list)
    age: str = ""
    season: str = ""
    summary: str = ""


_TIMELINE_ROW = re.compile(
    r"^\|\s*0*(\d+)(?:\s*[~～-]\s*0*(\d+))?\s*\|\s*([^|]+)\|\s*([^|]*)\|"
)


def parse_timeline_row(timeline_text: str, chapter: int) -> tuple[str, str, str]:
    """나이, 계절, 사건 요약."""
    age = ""
    season = ""
    summary = ""
    for line in (timeline_text or "").splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|\s*-+", line):
            continue
        m = _TIMELINE_ROW.match(line)
        if not m:
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if not (a <= chapter <= b):
            continue
        cell = m.group(3).strip()
        summary = m.group(4).strip()
        # **20**·두 번째 봄  /  19·초여름  /  18→19 직전·겨울
        cell_clean = cell.replace("**", "")
        if "·" in cell_clean:
            left, right = cell_clean.split("·", 1)
            age = left.strip()
            season = right.strip()
        else:
            age = cell_clean
        # 여러 행 매칭 시 더 좁은 범위(단일 장) 우선 — 단일 행이면 바로 반환
        if a == b == chapter:
            break
    return age, season, summary


def load_chapter_meta(novel_root: Path | str, chapter: int) -> ChapterMeta:
    novel = Path(novel_root)
    meta = ChapterMeta()
    cm = novel / "chapter_map.md"
    if cm.is_file():
        body, yt, ids = parse_chapter_map_row(cm.read_text(encoding="utf-8"), chapter)
        meta.body_title = body
        meta.youtube_title = yt
        meta.event_ids = ids
    tl = novel / "timeline.md"
    if tl.is_file():
        age, season, summary = parse_timeline_row(tl.read_text(encoding="utf-8"), chapter)
        meta.age = age
        meta.season = season
        meta.summary = summary
    return meta


def meta_status_line(meta: ChapterMeta) -> str:
    parts: list[str] = []
    if meta.body_title:
        parts.append(meta.body_title)
    age_season = "·".join(x for x in (meta.age, meta.season) if x)
    if age_season:
        parts.append(age_season)
    if meta.event_ids:
        if len(meta.event_ids) >= 2:
            parts.append(f"{meta.event_ids[0]}~{meta.event_ids[-1]}")
        else:
            parts.append(meta.event_ids[0])
    return " · ".join(parts) if parts else "(chapter_map/timeline에 해당 장 없음)"
