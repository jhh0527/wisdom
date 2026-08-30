# -*- coding: utf-8 -*-
"""부 줄거리 젠스파크 합본·저장."""

from __future__ import annotations

import re
from pathlib import Path

from volume_plot.paths import find_volume_plot_file, volume_plot_path
from volume_plot.volume_sources import (
    bible_excerpt,
    compress_volume_summary,
    extract_master_stem,
    last_chapter_excerpts,
    read_text,
)

VOLUME_START = "<<<VOLUME_START>>>"
VOLUME_END = "<<<VOLUME_END>>>"

_MARKER_RE = re.compile(
    re.escape(VOLUME_START) + r"\s*(.*?)\s*" + re.escape(VOLUME_END),
    re.DOTALL,
)

FALLBACK_RULES = """# 부 줄거리 작성 규칙 (내장)

- 한국어 문어체 무협. 한 채팅 = **한 부** 줄거리만.
- 이전 부·바이블과 **모순 금지**. 사망 인물 재등장·무단 설정 변경 금지.
- 출력은 마크다운: 부 제목, (있으면) 유튜브 제목 표, 마스터 줄기, `## 제N장` 절.
- 각 장 절에 본문 제목·사건 ID 구간(예: E230~E234)·나이·계절·핵심 사건.
- 다음 부 사건을 이 부에서 선취하지 말 것.
- 새 주요 인물·조직·사망은 「승인 대기」로만 표시.
"""


def extract_volume_body(text: str) -> str | None:
    if not text:
        return None
    m = _MARKER_RE.search(text)
    if not m:
        return None
    body = m.group(1).replace("\r\n", "\n").strip()
    return body or None


def build_volume_packet(
    *,
    novel_root: Path | str,
    volume: int,
    chapter_range: str = "",
    goals: str = "",
    include_write_rules: bool = True,
    include_characters: bool = True,
    include_foreshadowing: bool = True,
    include_events_tail: bool = True,
    prev_last_chapters: int = 2,
) -> tuple[str, list[str]]:
    """젠스파크 붙여넣기 합본."""
    notes: list[str] = []
    parts: list[str] = []
    novel = Path(novel_root).expanduser()
    vol = int(volume)

    parts.append(
        f"# 젠스파크 붙여넣기 — 제{vol}부 줄거리\n"
        f"한 채팅 = 제{vol}부 줄거리만. 아래 순서를 따른 뒤 구분자로 감싸 출력."
    )

    if include_write_rules:
        wr = novel / "WRITE_RULES.md"
        if wr.is_file():
            body = bible_excerpt(wr, max_chars=5000)
            parts.append("===== WRITE_RULES.md (발췌) =====\n" + body)
        else:
            parts.append("===== 작성 규칙 (내장) =====\n" + FALLBACK_RULES.strip())
            notes.append("WRITE_RULES.md 없음 — 내장 규칙")

    if include_characters:
        ch = novel / "characters.md"
        if ch.is_file():
            parts.append(
                "===== characters.md (발췌) =====\n"
                + bible_excerpt(ch, max_chars=4000)
            )
        else:
            notes.append("characters.md 없음")

    if include_foreshadowing:
        fs = novel / "foreshadowing.md"
        if fs.is_file():
            parts.append(
                "===== foreshadowing.md (발췌) =====\n"
                + bible_excerpt(fs, max_chars=2500)
            )
        else:
            notes.append("foreshadowing.md 없음")

    if include_events_tail:
        ev = novel / "events.md"
        if ev.is_file():
            # 파일 끝(최근 블록) 위주
            raw = read_text(ev).strip()
            tail = raw[-3500:] if len(raw) > 3500 else raw
            parts.append("===== events.md (끝부분) =====\n" + tail)
            if len(raw) > 3500:
                notes.append("events.md 끝 3500자만")
        else:
            notes.append("events.md 없음")

    # 이전 부: 직전 = 줄기+말미 장 / 그 이전 = 초압축
    if vol <= 1:
        notes.append("1부 — 이전 부 생략")
    else:
        prev = vol - 1
        prev_path = find_volume_plot_file(novel, prev)
        if prev_path is None:
            notes.append(f"{prev}부 줄거리 파일 없음")
        else:
            prev_text = read_text(prev_path)
            stem = extract_master_stem(prev_text, max_chars=1500)
            tail = last_chapter_excerpts(
                prev_text, n=max(1, prev_last_chapters), max_chars=4500
            )
            block = (
                f"===== 직전 부 ({prev}부 · {prev_path.name}) =====\n"
                f"### 마스터 줄기\n{stem}\n\n"
                f"### 말미 {prev_last_chapters}장\n{tail}"
            )
            parts.append(block)

        for older in range(1, prev):
            op = find_volume_plot_file(novel, older)
            if op is None:
                notes.append(f"{older}부 줄거리 없음 — 요약 생략")
                continue
            summary = compress_volume_summary(read_text(op), max_chars=800)
            parts.append(
                f"===== 이전 부 요약 ({older}부 · {op.name}) =====\n{summary}"
            )

    goals_block = (goals or "").strip() or (
        f"제{vol}부 줄거리를 작성한다. "
        "유튜브 제목 표 + 마스터 줄기 + 장별 `## 제N장` 절."
    )
    cr = (chapter_range or "").strip()
    range_line = f"장 범위: {cr}\n" if cr else ""

    parts.append(
        "===== 작성 지시 =====\n"
        f"{range_line}"
        f"{goals_block}\n\n"
        "이전 부 말미 상태·바이블(사망·납치·정체·복선)과 모순되지 않게 쓸 것.\n"
        "부 첫 장은 직전 부 끝과 이어질 것.\n"
        "출력은 마크다운 부 줄거리만.\n\n"
        "【필수】 출력 전체를 아래 구분자로 감싼다. 구분자 밖에는 쓰지 말 것.\n"
        f"{VOLUME_START}\n"
        f"(# 제{vol}부 … 전체 마크다운)\n"
        f"{VOLUME_END}"
    )

    return "\n\n".join(parts).strip() + "\n", notes


def save_volume_plot(novel_root: Path | str, volume: int, text: str) -> Path:
    path = volume_plot_path(novel_root, volume)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (text or "").replace("\r\n", "\n").strip()
    # 구분자 있으면 사이만
    extracted = extract_volume_body(body)
    if extracted:
        body = extracted
    if body and not body.endswith("\n"):
        body += "\n"
    path.write_text(body, encoding="utf-8")
    return path.resolve()
