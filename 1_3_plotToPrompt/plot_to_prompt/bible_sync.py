# -*- coding: utf-8 -*-
"""줄거리 → chapter_map · events · 부 줄거리 동기화."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from plot_to_prompt.brief_builder import expand_event_field, parse_chapter_map_row

_CHAPTER_HEAD = re.compile(
    r"^##\s*제\s*0*(\d+)\s*장\b(.*)$",
    re.MULTILINE,
)
_VOLUME_HEAD = re.compile(r"^##\s*(\d+)\s*부\b", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\|\s*-+")


@dataclass
class SyncResult:
    notes: list[str] = field(default_factory=list)
    chapter_map: bool = False
    events: bool = False
    volume_plot: bool = False

    def summary(self) -> str:
        parts = []
        if self.chapter_map:
            parts.append("chapter_map")
        if self.events:
            parts.append("events")
        if self.volume_plot:
            parts.append("부줄거리")
        base = "동기화: " + (", ".join(parts) if parts else "변경 없음")
        if self.notes:
            return base + " · " + "; ".join(self.notes[:6])
        return base


def default_event_id_range(chapter: int) -> list[str]:
    """장 14 → E140..E145 (기존 검신 규칙과 동일 패턴)."""
    ch = max(1, int(chapter))
    base = ch * 10
    return [f"E{base + i}" for i in range(0, 6)]


def event_ids_display(ids: list[str]) -> str:
    if not ids:
        return ""
    if len(ids) == 1:
        return ids[0]
    first, last = ids[0], ids[-1]
    m1 = re.match(r"E(\d+)$", first, re.I)
    m2 = re.match(r"E(\d+)$", last, re.I)
    if m1 and m2 and int(m2.group(1)) == int(m1.group(1)) + len(ids) - 1:
        return f"{first}~{last}"
    return ", ".join(ids)


def infer_volume_number(novel_root: Path, chapter: int) -> int | None:
    """chapter_map 절 또는 N부 줄거리 헤더로 부 번호 추정."""
    vol = _volume_from_map_sections(novel_root, chapter)
    if vol is not None:
        return vol
    for p in sorted(novel_root.glob("*부")):
        if not p.is_dir():
            continue
        m = re.match(r"^(\d+)부$", p.name)
        if not m:
            continue
        plot = _volume_plot_path(novel_root, int(m.group(1)))
        if not plot.is_file():
            continue
        try:
            text = plot.read_text(encoding="utf-8")
        except OSError:
            continue
        for hm in _CHAPTER_HEAD.finditer(text):
            if int(hm.group(1)) == chapter:
                return int(m.group(1))
    return None


def _volume_from_map_sections(novel_root: Path, chapter: int) -> int | None:
    cm = novel_root / "chapter_map.md"
    if not cm.is_file():
        return None
    text = cm.read_text(encoding="utf-8")
    sections: list[tuple[int, int, int]] = []  # vol, start_line, end
    lines = text.splitlines()
    vol_starts: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        vm = _VOLUME_HEAD.match(line.strip())
        if vm:
            vol_starts.append((i, int(vm.group(1))))
    for idx, (start, vol) in enumerate(vol_starts):
        end = vol_starts[idx + 1][0] if idx + 1 < len(vol_starts) else len(lines)
        chapters: list[int] = []
        for line in lines[start:end]:
            if not line.strip().startswith("|"):
                continue
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if cols and cols[0].isdigit():
                chapters.append(int(cols[0]))
        if chapter in chapters:
            return vol
        if chapters and min(chapters) <= chapter <= max(chapters):
            return vol
    return None


def _volume_plot_path(novel_root: Path, volume: int) -> Path:
    return novel_root / f"{volume}부" / f"제{volume}부줄거리.md"


def _title_from_plot(plot: str, fallback: str = "") -> str:
    t = (plot or "").strip().splitlines()[0].strip() if (plot or "").strip() else ""
    t = re.sub(r"^#+\s*", "", t)
    t = re.sub(r"^제\s*\d+\s*장[.\s—\-]*", "", t)
    if len(t) > 40:
        t = t[:40].rstrip() + "…"
    return t or fallback or "(제목 미정)"


def upsert_chapter_map(
    novel_root: Path,
    chapter: int,
    *,
    body_title: str,
    event_ids: list[str],
    youtube_title: str = "",
) -> str | None:
    """chapter_map 행 upsert. 변경 메시지 또는 None."""
    path = novel_root / "chapter_map.md"
    ids = event_ids or default_event_id_range(chapter)
    id_field = event_ids_display(ids)
    title = (body_title or "").strip() or _title_from_plot("", f"제{chapter}장")
    yt = (youtube_title or "").strip()

    if not path.is_file():
        path.write_text(
            f"# 장 ↔ 사건 맵\n\n"
            f"| 장 | 본문 제목 | 사건 ID | 유튜브 제목 |\n"
            f"|----|-----------|---------|-------------|\n"
            f"| {chapter} | {title} | {id_field} | {yt} |\n",
            encoding="utf-8",
        )
        return f"chapter_map.md 생성 · {chapter}행"

    text = path.read_text(encoding="utf-8")
    existing_body, existing_yt, existing_ids = parse_chapter_map_row(text, chapter)
    if existing_body or existing_ids:
        # 갱신: 제목/ID가 비어 있을 때만 채움, 유튜브는 유지
        new_title = existing_body or title
        new_ids = event_ids_display(existing_ids) if existing_ids else id_field
        new_yt = existing_yt or yt
        if (
            new_title == existing_body
            and new_ids == event_ids_display(existing_ids)
            and new_yt == existing_yt
        ):
            return None
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        replaced = False
        for line in lines:
            raw = line.strip()
            if raw.startswith("|") and not _TABLE_SEP.match(raw):
                cols = [c.strip() for c in raw.strip("|").split("|")]
                if cols and cols[0].isdigit() and int(cols[0]) == chapter:
                    out.append(
                        f"| {chapter} | {new_title} | {new_ids} | {new_yt} |\n"
                    )
                    replaced = True
                    continue
            out.append(line if line.endswith("\n") else line + "\n")
        if replaced:
            path.write_text("".join(out), encoding="utf-8")
            return f"chapter_map {chapter}행 갱신"
        return None

    # 새 행 삽입: 같은 부 표에서 정렬 위치에
    insert_line = f"| {chapter} | {title} | {id_field} | {yt} |"
    lines = text.splitlines()
    insert_at: int | None = None
    last_table_line: int | None = None
    for i, line in enumerate(lines):
        raw = line.strip()
        if not raw.startswith("|") or _TABLE_SEP.match(raw):
            continue
        cols = [c.strip() for c in raw.strip("|").split("|")]
        if not cols or not cols[0].isdigit():
            continue
        last_table_line = i
        n = int(cols[0])
        if n > chapter and insert_at is None:
            insert_at = i
    if insert_at is None:
        insert_at = (last_table_line + 1) if last_table_line is not None else len(lines)
    lines.insert(insert_at, insert_line)
    path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else "\n"), encoding="utf-8")
    return f"chapter_map {chapter}행 추가"


def upsert_events(
    novel_root: Path,
    chapter: int,
    event_ids: list[str],
    *,
    body_title: str,
    plot: str,
) -> str | None:
    """없는 사건 ID만 『예정』으로 추가. 확정 행은 건드리지 않음."""
    path = novel_root / "events.md"
    ids = event_ids or default_event_id_range(chapter)
    if not path.is_file():
        rows = "\n".join(
            f"| {eid} | (줄거리) {body_title or f'제{chapter}장'} | — | 예정 |"
            for eid in ids
        )
        path.write_text(
            f"# 사건 타임라인\n\n"
            f"상태: `확정` / `예정` / `폐기`\n\n"
            f"### 블록 {ids[0]} — 제{chapter}장\n\n"
            f"| ID | 사건 | 선후 | 상태 |\n"
            f"|----|------|------|------|\n"
            f"{rows}\n",
            encoding="utf-8",
        )
        return f"events.md 생성 · {ids[0]}~"

    text = path.read_text(encoding="utf-8")
    missing = [eid for eid in ids if not re.search(rf"\|\s*{re.escape(eid)}\s*\|", text)]
    if not missing:
        return None

    title = (body_title or "").strip() or _title_from_plot(plot, f"제{chapter}장")
    summary = _title_from_plot(plot, title)
    block_id = ids[0]
    rows = "\n".join(
        f"| {eid} | {summary} | — | 예정 |" for eid in missing
    )
    block = (
        f"\n\n### 블록 {block_id} — 제{chapter}장 (GUI 동기화·예정)\n\n"
        f"| ID | 사건 | 선후 | 상태 |\n"
        f"|----|------|------|------|\n"
        f"{rows}\n"
    )
    path.write_text(text.rstrip() + block, encoding="utf-8")
    return f"events 예정 추가 {', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}"


def upsert_volume_plot(
    novel_root: Path,
    chapter: int,
    plot: str,
    *,
    body_title: str,
    event_ids: list[str],
    volume: int | None = None,
) -> str | None:
    """N부/제N부줄거리에 ## 제N장 절 upsert."""
    vol = volume if volume is not None else infer_volume_number(novel_root, chapter)
    if vol is None:
        return "부 번호 미확정(부줄거리 생략 — chapter_map에 부 절·장 행 확인)"
    ids = event_ids or default_event_id_range(chapter)
    id_field = event_ids_display(ids)
    title = (body_title or "").strip() or _title_from_plot(plot, f"제{chapter}장")
    body = (plot or "").strip()
    if not body:
        return None

    folder = novel_root / f"{vol}부"
    folder.mkdir(parents=True, exist_ok=True)
    path = _volume_plot_path(novel_root, vol)
    section = f"## 제{chapter}장. {title} — {id_field}\n\n{body}\n"

    if not path.is_file():
        path.write_text(
            f"# 제{vol}부 줄거리\n\n"
            f"> 사건 ID: `events.md` · 장↔제목: `chapter_map.md`\n\n"
            f"{section}\n",
            encoding="utf-8",
        )
        return f"제{vol}부줄거리.md 생성 · 제{chapter}장"

    text = path.read_text(encoding="utf-8")
    matches = list(_CHAPTER_HEAD.finditer(text))
    for i, m in enumerate(matches):
        if int(m.group(1)) != chapter:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        new_text = text[:start] + section + "\n" + text[end:].lstrip("\n")
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return f"제{vol}부줄거리 제{chapter}장 갱신"
        return None

    # 삽입 위치: 다음 장 번호보다 작은 절 뒤
    insert_at = len(text)
    for m in matches:
        if int(m.group(1)) > chapter:
            insert_at = m.start()
            break
    new_text = text[:insert_at].rstrip() + "\n\n" + section + "\n" + text[insert_at:].lstrip()
    path.write_text(new_text, encoding="utf-8")
    return f"제{vol}부줄거리 제{chapter}장 추가"


def sync_plot_to_bible(
    novel_root: Path | str,
    chapter: int,
    plot: str,
    *,
    body_title: str = "",
    youtube_title: str = "",
    event_ids: list[str] | None = None,
) -> SyncResult:
    """BRIEF 저장과 함께 호출 — map / events / 부줄거리."""
    root = Path(novel_root)
    result = SyncResult()
    if not root.is_dir():
        result.notes.append("작품 폴더 없음")
        return result

    meta_body, meta_yt, meta_ids = ("", "", [])
    cm = root / "chapter_map.md"
    if cm.is_file():
        meta_body, meta_yt, meta_ids = parse_chapter_map_row(
            cm.read_text(encoding="utf-8"), chapter
        )

    ids = list(event_ids or []) or list(meta_ids) or default_event_id_range(chapter)
    title = (body_title or meta_body or "").strip() or _title_from_plot(plot, f"제{chapter}장")
    yt = (youtube_title or meta_yt or "").strip()

    msg = upsert_chapter_map(
        root, chapter, body_title=title, event_ids=ids, youtube_title=yt
    )
    if msg:
        result.chapter_map = True
        result.notes.append(msg)

    msg = upsert_events(root, chapter, ids, body_title=title, plot=plot)
    if msg:
        result.events = True
        result.notes.append(msg)

    msg = upsert_volume_plot(
        root, chapter, plot, body_title=title, event_ids=ids
    )
    if msg:
        if "생략" in msg or "미확정" in msg:
            result.notes.append(msg)
        else:
            result.volume_plot = True
            result.notes.append(msg)

    return result
