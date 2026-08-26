# -*- coding: utf-8 -*-
"""기존 BRIEF로 젠스파크 합본·tts 저장."""

from __future__ import annotations

import re
from pathlib import Path

from plot_to_prompt.prompt_pack import load_write_rules

_PREV_TAIL = 1200
_CHARS_MAX = 4000

CHAPTER_START = "<<<CHAPTER_START>>>"
CHAPTER_END = "<<<CHAPTER_END>>>"

_MARKER_RE = re.compile(
    re.escape(CHAPTER_START) + r"\s*(.*?)\s*" + re.escape(CHAPTER_END),
    re.DOTALL,
)


def extract_chapter_body(text: str) -> str | None:
    """START/END 사이 본문. 없으면 None."""
    if not text:
        return None
    m = _MARKER_RE.search(text)
    if not m:
        return None
    body = m.group(1).replace("\r\n", "\n").strip()
    return body or None


def resolve_brief_file(novel_root: Path | str, chapter: int) -> Path | None:
    base = Path(novel_root).expanduser() / "briefs"
    if not base.is_dir():
        return None
    for name in (
        f"CHAPTER_{chapter}.md",
        f"CHAPTER_{chapter:02d}.md",
        f"CHAPTER_{chapter:03d}.md",
    ):
        p = base / name
        if p.is_file():
            return p.resolve()
    return None


def ensure_tts(work_root: Path | str) -> Path:
    root = Path(work_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    t = root / "tts"
    t.mkdir(parents=True, exist_ok=True)
    return t


def chapter_tts_path(work_root: Path | str, chapter: int) -> Path:
    return Path(work_root).expanduser() / "tts" / f"{int(chapter)}.txt"


def prev_chapter_tail(work_root: Path | str, chapter: int, *, max_chars: int = _PREV_TAIL) -> str:
    if chapter <= 1:
        return ""
    prev = chapter_tts_path(work_root, chapter - 1)
    if not prev.is_file():
        return ""
    try:
        text = prev.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def build_packet_from_brief(
    *,
    novel_root: Path | str,
    work_root: Path | str,
    chapter: int,
) -> tuple[str, list[str]]:
    """디스크 BRIEF(+ WRITE_RULES·characters·직전 tts 꼬리)로 합본."""
    notes: list[str] = []
    parts: list[str] = []
    novel = Path(novel_root).expanduser()

    wr = novel / "WRITE_RULES.md"
    rules = load_write_rules(wr if wr.is_file() else None)
    parts.append("===== WRITE_RULES.md =====\n" + rules)
    if not wr.is_file():
        notes.append("WRITE_RULES.md 없음 — 내장 규칙 사용")

    bp = resolve_brief_file(novel, chapter)
    if bp is None:
        notes.append(f"briefs/CHAPTER_{chapter}.md 없음")
    else:
        parts.append(f"===== {bp.name} =====\n" + bp.read_text(encoding="utf-8-sig").strip())

    chars = novel / "characters.md"
    if chars.is_file():
        body = chars.read_text(encoding="utf-8-sig").strip()
        if len(body) > _CHARS_MAX:
            body = body[:_CHARS_MAX] + "\n…(이하 생략 — 필요 인물만 추가)…"
            notes.append("characters.md 앞 4000자만")
        parts.append("===== characters.md (발췌) =====\n" + body)
    else:
        notes.append("characters.md 없음")

    tail = prev_chapter_tail(work_root, chapter)
    if tail:
        parts.append(f"===== 직전 장 꼬리 ({chapter - 1}.txt) =====\n" + tail)
    else:
        notes.append(f"직전 tts/{chapter - 1}.txt 없음 — 꼬리 생략")

    parts.append(
        "===== 작성 지시 =====\n"
        f"{chapter}장 본문만 작성하라. WRITE_RULES와 BRIEF 비트를 따른다.\n"
        "제목 한 줄 다음 본문만. 메타·비트 번호·설명 금지.\n"
        "목표 분량 9,000~11,000자.\n\n"
        "【필수】 출력 전체를 아래 구분자로 감싼다. 구분자 밖에는 아무 글도 쓰지 말 것.\n"
        f"{CHAPTER_START}\n"
        "(제목 한 줄)\n"
        "(본문)\n"
        f"{CHAPTER_END}"
    )
    return "\n\n".join(parts).strip() + "\n", notes


def save_chapter_to_tts(work_root: Path | str, chapter: int, text: str) -> Path:
    ensure_tts(work_root)
    path = chapter_tts_path(work_root, chapter)
    body = (text or "").replace("\r\n", "\n").strip()
    if body and not body.endswith("\n"):
        body += "\n"
    path.write_text(body, encoding="utf-8")
    return path.resolve()
