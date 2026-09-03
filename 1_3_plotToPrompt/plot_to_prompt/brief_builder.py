# -*- coding: utf-8 -*-
"""줄거리 → BRIEF 마크다운 조립 (LLM 없이 구조화)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_SENT_SPLIT = re.compile(r"(?<=[.!?。！？…])\s+|(?<=다\.)\s+|(?<=요\.)\s+|\n+")


@dataclass
class BriefInput:
    chapter: int
    body_title: str = ""
    youtube_title: str = ""
    age: str = ""
    season: str = ""
    place: str = ""
    event_ids: list[str] = field(default_factory=list)
    plot: str = ""
    cast: str = ""
    forbid: str = ""
    foreshadow: str = ""
    ending_hook: str = ""
    prev_state: str = ""
    target_chars: str = "9000~11000자"


def split_plot_to_beats(plot: str, *, min_n: int = 8, max_n: int = 12) -> list[str]:
    text = (plot or "").strip()
    if not text:
        return [f"(비트 {i}: 줄거리에서 채울 것)" for i in range(1, min_n + 1)]

    raw = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    if len(raw) == 1:
        raw = [
            p.strip()
            for p in re.split(r"[，,;；]\s*|\s+(?:그리고|그러나|하지만|또한)\s+", text)
            if p.strip()
        ]

    if not raw:
        raw = [text]

    if len(raw) > max_n:
        merged: list[str] = []
        chunk = max(1, len(raw) // max_n)
        i = 0
        while i < len(raw) and len(merged) < max_n:
            take = raw[i : i + chunk]
            if len(merged) == max_n - 1:
                take = raw[i:]
            merged.append(" ".join(take).strip())
            i += chunk
        raw = merged

    while len(raw) < min_n:
        raw.append(f"밀도 보강 {len(raw) + 1}: 감각·내면·대화 (신규 사건 금지)")

    return raw[:max_n]


def _split_md_table_row(line: str) -> list[str]:
    """마크다운 표 한 줄 → 칸. 칸 안의 ``\\|`` 는 ``|`` 로 복원."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    protected = s.replace("\\|", "\x00")
    return [c.strip().replace("\x00", "|") for c in protected.split("|")]


def parse_chapter_map_row(chapter_map_text: str, chapter: int) -> tuple[str, str, list[str]]:
    """본문 제목, 유튜브 제목, 사건 ID 목록."""
    body = ""
    yt = ""
    ids: list[str] = []
    for line in (chapter_map_text or "").splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|\s*-+", line):
            continue
        cols = _split_md_table_row(line)
        if len(cols) < 3:
            continue
        if not cols[0].isdigit() or int(cols[0]) != chapter:
            continue
        body = cols[1]
        id_field = cols[2]
        yt = "|".join(cols[3:]).strip() if len(cols) > 3 else ""
        ids = expand_event_field(id_field)
        break
    return body, yt, ids


def expand_event_field(field: str) -> list[str]:
    """'E230~E234' / 'E230, E231' → ['E230', ...]."""
    field = field.replace("～", "~").replace("—", "-")
    out: list[str] = []
    for part in re.split(r"\s*,\s*", field):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(E\d+)\s*[~\-]\s*E?(\d+)", part, re.I)
        if m:
            a, b = int(m.group(1)[1:]), int(m.group(2))
            for n in range(a, b + 1):
                out.append(f"E{n}")
        else:
            digits = re.match(r"[Ee](\d+)", part)
            if digits:
                out.append(f"E{digits.group(1)}")
            else:
                out.append(part)
    return out


def build_brief_markdown(inp: BriefInput) -> str:
    beats = split_plot_to_beats(inp.plot)
    ch = inp.chapter
    title = inp.body_title.strip() or f"제{ch}장"
    yt = inp.youtube_title.strip() or "(확정 전이면 비워 둠)"

    event_lines: list[str] = []
    if inp.event_ids:
        for eid in inp.event_ids:
            event_lines.append(f"- {eid}")
    else:
        event_lines.append("- (events.md / chapter_map에서 ID를 채울 것)")

    cast = inp.cast.strip() or "- 진무한\n- 한백강"
    if not cast.startswith("-"):
        cast = "\n".join(f"- {line.strip()}" for line in cast.splitlines() if line.strip()) or "- 진무한\n- 한백강"

    forbid_default = (
        "- 새 조직 / 새 주요 인물 / 사망·자결·납치 (BRIEF에 없으면)\n"
        "- 다음 장 사건 선취\n"
        "- 기존 사건 결과 변경\n"
        "- events.md에 없는 사건"
    )
    forbid = inp.forbid.strip() or forbid_default
    if inp.forbid.strip() and not forbid.startswith("-"):
        forbid = "\n".join(f"- {line.strip()}" for line in forbid.splitlines() if line.strip())

    foreshadow = inp.foreshadow.strip() or "- 없음"
    if not foreshadow.startswith("-"):
        foreshadow = "\n".join(f"- {line.strip()}" for line in foreshadow.splitlines() if line.strip())

    hook = inp.ending_hook.strip() or "환의 실체가 드러나며 다음 장 충돌을 예고한다."
    prev = inp.prev_state.strip() or "직전 장 사건의 여파가 이어지는 상태."

    beat_block = "\n".join(f"{i}. {b}" for i, b in enumerate(beats, 1))
    proper = _guess_proper_nouns(inp.plot)

    return f"""# BRIEF — CHAPTER_{ch:02d}

장: {ch}
본문 제목: {title}
유튜브 제목: {yt}
목표 분량: {inp.target_chars}

시점:
- 나이: {inp.age.strip() or "(timeline.md)"}
- 계절: {inp.season.strip() or "(timeline.md)"}
- 장소: {inp.place.strip() or "줄거리 기준 핵심 현장"}

이 장 사건 ID (이것만 처리):
{chr(10).join(event_lines)}

등장 (이 장만):
{cast}

반드시 일어나는 일 (비트 — 순서 고정):
{beat_block}

숫자·고유명사 고정:
{proper}

절대 하지 말 것:
{forbid}

복선:
{foreshadow}

종료 훅:
- {hook}

직전 장에서 이어질 상태:
- {prev}

---
줄거리 원문 (~700자 입력):
{inp.plot.strip()}
"""


def _guess_proper_nouns(plot: str) -> str:
    names = sorted(set(re.findall(r"[가-힣]{2,4}(?:\([一-龥]{1,8}\))?", plot or "")))
    stop = {"그러나", "그리고", "하지만", "또한", "이번", "오늘", "저녁", "아침", "자신", "그자", "그곳"}
    picked = [n for n in names if n not in stop and len(n) >= 2][:12]
    if not picked:
        return "- (본문·events와 동일하게 고정)"
    return "\n".join(f"- {n}" for n in picked)
