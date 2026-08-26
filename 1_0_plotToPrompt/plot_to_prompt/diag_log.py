# -*- coding: utf-8 -*-
"""진단 로그 (파일 + GUI 리스너)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

_listeners: list = []
_log_path: Path | None = None


def add_listener(fn) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def remove_listener(fn) -> None:
    try:
        _listeners.remove(fn)
    except ValueError:
        pass


def log_path() -> Path | None:
    return _log_path


def start_session(path: Path | str, *, title: str = "") -> Path:
    global _log_path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _log_path = p
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"===== {stamp} {title} ====="
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    _emit(line)
    return p


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    if _log_path is not None:
        try:
            with _log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    _emit(line)


def _emit(line: str) -> None:
    for fn in list(_listeners):
        try:
            fn(line)
        except Exception:
            pass
