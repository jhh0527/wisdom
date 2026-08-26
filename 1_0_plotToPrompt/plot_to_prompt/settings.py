# -*- coding: utf-8 -*-
"""GUI 설정 저장."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_NAME = "plot_to_prompt_gui_config.json"


def config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_NAME
    return Path(__file__).resolve().parents[1] / "dist" / CONFIG_NAME


def load_gui_settings() -> dict[str, str]:
    p = config_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("novel_root", "work_root", "last_chapter"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()
        elif key == "last_chapter" and isinstance(v, (int, float)):
            out[key] = str(int(v))
    return out


def save_gui_settings(
    *,
    novel_root: str,
    last_chapter: str = "",
    work_root: str = "",
) -> None:
    try:
        from wisdom_workspace import touch_workspace_from_path

        touch_workspace_from_path(novel_root)
        if work_root.strip():
            touch_workspace_from_path(work_root)
    except ImportError:
        pass
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = load_gui_settings()
    data: dict[str, str] = dict(prev)
    data["novel_root"] = novel_root
    if last_chapter.strip():
        data["last_chapter"] = last_chapter.strip()
    if work_root.strip():
        data["work_root"] = work_root.strip()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
