# -*- coding: utf-8 -*-
"""작품·산출 경로."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIRNAME = "1_3_plotToPrompt"
NOVEL_REL = Path("무협극장") / "검신귀환록"


def _ensure_wisdom_on_path(from_file: str | Path) -> None:
    for base in [Path.cwd(), *Path(from_file).resolve().parents]:
        if (base / "wisdom_root.py").is_file():
            s = str(base)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


_ensure_wisdom_on_path(__file__)
from wisdom_root import module_dir, resolve_wisdom_root  # noqa: E402


def project_root() -> Path:
    found = module_dir(PROJECT_DIRNAME)
    if found.is_dir():
        return found
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent.parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p
    return start


def default_novel_root() -> Path:
    cand = resolve_wisdom_root() / NOVEL_REL
    if cand.is_dir():
        return cand
    return resolve_wisdom_root() / "무협극장" / "검신귀환록"


def default_output_dir(novel_root: Path | None = None) -> Path:
    root = novel_root if novel_root is not None else default_novel_root()
    briefs = root / "briefs"
    if briefs.is_dir() or root.is_dir():
        return briefs
    return project_root() / "output"


def write_rules_path(novel_root: Path) -> Path:
    return novel_root / "WRITE_RULES.md"


def template_path(novel_root: Path) -> Path:
    return novel_root / "briefs" / "_TEMPLATE.md"


def chapter_map_path(novel_root: Path) -> Path:
    return novel_root / "chapter_map.md"


def events_path(novel_root: Path) -> Path:
    return novel_root / "events.md"


def brief_path(novel_root: Path, chapter: int) -> Path:
    """저장 기본 경로 (CHAPTER_23.md). 읽기는 tts_packet.resolve_brief_file 사용."""
    return novel_root / "briefs" / f"CHAPTER_{chapter:02d}.md"


def default_work_root() -> Path:
    try:
        from wisdom_workspace import get_workspace_dir

        ws = get_workspace_dir()
        if ws is not None:
            return ws
    except ImportError:
        pass
    return project_root() / "output"


def default_log_path() -> Path:
    """exe 옆 또는 모듈 dist/logs."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = project_root() / "dist"
    return base / "logs" / "plot_to_prompt.log"


_CHAPTER_DIR = re.compile(r"^(?:제\s*)?(\d+)\s*장$", re.I)
_VOLUME_DIR = re.compile(r"^(\d+)\s*부$", re.I)


def parse_chapter_from_path(path: Path | str | None) -> int | None:
    """작업 경로에서 장 번호 추출. 예: ``…/2부/14장`` → 14, ``…/14장/tts`` → 14."""
    if not path:
        return None
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        p = Path(path).expanduser()
    for part in [p.name, *[x.name for x in p.parents]]:
        m = _CHAPTER_DIR.match(part.strip())
        if m:
            n = int(m.group(1))
            if n >= 1:
                return n
    return None


def parse_volume_from_path(path: Path | str | None) -> int | None:
    if not path:
        return None
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        p = Path(path).expanduser()
    for part in [p.name, *[x.name for x in p.parents]]:
        m = _VOLUME_DIR.match(part.strip())
        if m:
            return int(m.group(1))
    return None


def infer_novel_root_from_work(path: Path | str | None) -> Path | None:
    """``…/작품/2부/14장`` → 작품 폴더 (chapter_map·briefs 있는 곳)."""
    if not path:
        return None
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        p = Path(path).expanduser()
    if not p.exists():
        return None
    cur = p if p.is_dir() else p.parent
    for _ in range(8):
        if (cur / "chapter_map.md").is_file() or (cur / "briefs").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None
