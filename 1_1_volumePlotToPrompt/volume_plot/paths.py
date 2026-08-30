# -*- coding: utf-8 -*-
"""작품·부 줄거리 경로."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIRNAME = "1_1_volumePlotToPrompt"
NOVEL_REL = Path("workspace") / "swardmaster"

_VOLUME_DIR = re.compile(r"^(\d+)\s*부$", re.I)


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
    root = resolve_wisdom_root()
    for cand in (
        root / NOVEL_REL,
        root / "workspace" / "swardmaster",
        root / "무협극장" / "검신귀환록",
    ):
        if cand.is_dir():
            return cand
    return root / NOVEL_REL


def volume_dir(novel_root: Path | str, volume: int) -> Path:
    return Path(novel_root).expanduser() / f"{int(volume)}부"


def volume_plot_path(novel_root: Path | str, volume: int) -> Path:
    """저장 기본 경로 ``N부/제N부줄거리.md``."""
    return volume_dir(novel_root, volume) / f"제{int(volume)}부줄거리.md"


def find_volume_plot_file(novel_root: Path | str, volume: int) -> Path | None:
    """존재하는 부 줄거리·시놉시스 파일."""
    base = volume_dir(novel_root, volume)
    if not base.is_dir():
        return None
    preferred = [
        f"제{volume}부줄거리.md",
        f"제{volume}부 줄거리.md",
        f"제{volume}부 시놉시스.txt",
        f"제{volume}부시놉시스.txt",
    ]
    for name in preferred:
        p = base / name
        if p.is_file():
            return p.resolve()
    # 느슨: *줄거리* / *시놉*
    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue
        n = p.name
        if "줄거리" in n or "시놉" in n:
            return p.resolve()
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


def infer_novel_root_from_path(path: Path | str | None) -> Path | None:
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


def default_log_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = project_root() / "dist"
    return base / "logs" / "volume_plot.log"
