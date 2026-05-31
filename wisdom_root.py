# -*- coding: utf-8 -*-
"""wisdom 워크스페이스(IDE·탐색기에서 연 폴더) 루트 — 모듈 간 경로의 공통 기준."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MARKER_DIRS = ("3_ttsToVoice", "5_video", "4_srtToImage", "1_textTo700Text")

_installed = False


def looks_like_wisdom_root(p: Path) -> bool:
    try:
        r = p.resolve()
    except OSError:
        return False
    hits = sum(1 for name in MARKER_DIRS if (r / name).is_dir())
    return hits >= 2


def _walk_up(start: Path, *, max_depth: int = 12) -> Path | None:
    p = start.resolve()
    for _ in range(max_depth):
        if looks_like_wisdom_root(p):
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return None


def _candidate_starts() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            key = str(p.resolve())
        except OSError:
            return
        if key not in seen:
            seen.add(key)
            out.append(Path(key))

    add(Path.cwd())
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        add(exe.parent)
        if exe.parent.name == "dist":
            add(exe.parent.parent)
            add(exe.parent.parent.parent)
    here = Path(__file__).resolve().parent
    add(here)
    for parent in here.parents:
        add(parent)
    return out


def resolve_wisdom_root() -> Path:
    """wisdom 워크스페이스 루트.

    1. ``WISDOM_ROOT`` 환경 변수
    2. 현재 작업 폴더(열린 폴더) — wisdom 구조면 우선
    3. exe·``wisdom_root.py`` 위치에서 상위 탐색
    4. 작업 폴더 그대로(열린 폴더를 루트로 간주)
    """
    env = os.environ.get("WISDOM_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    cwd = Path.cwd().resolve()
    if looks_like_wisdom_root(cwd):
        return cwd

    for start in _candidate_starts():
        if start == cwd:
            continue
        found = _walk_up(start)
        if found is not None:
            return found

    return cwd


def _ensure_importable() -> None:
    root = resolve_wisdom_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        mp = str(meipass)
        if mp not in sys.path:
            sys.path.insert(0, mp)


def install(*, chdir: bool = True) -> Path:
    """GUI·run 스크립트 시작 시 1회: import 경로·작업 폴더를 wisdom 루트로."""
    global _installed
    _ensure_importable()
    root = resolve_wisdom_root()
    if chdir:
        try:
            os.chdir(root)
        except OSError:
            pass
    _installed = True
    return root


def bootstrap() -> Path:
    """``install()`` 별칭 — run_*_gui 진입점에서 호출."""
    return install()


def module_dir(name: str) -> Path:
    return resolve_wisdom_root() / name


def module_output(name: str) -> Path:
    return module_dir(name) / "output"


def find_module_dir(name: str) -> Path | None:
    """``name`` 모듈 폴더가 있으면 반환, 없으면 None."""
    p = module_dir(name)
    return p if p.is_dir() else None
