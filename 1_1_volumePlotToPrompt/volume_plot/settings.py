# -*- coding: utf-8 -*-
"""GUI 설정 저장."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_NAME = "volume_plot_gui_config.json"


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
    for key in ("novel_root", "volume", "chapter_range", "clip_watch"):
        v = data.get(key)
        if key == "clip_watch":
            if isinstance(v, bool):
                out[key] = "1" if v else "0"
            elif isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
                out[key] = "1"
            elif isinstance(v, str) and v.strip().lower() in ("0", "false", "no", "off"):
                out[key] = "0"
            continue
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()
        elif key == "volume" and isinstance(v, (int, float)):
            out[key] = str(int(v))
    return out


def save_gui_settings(
    *,
    novel_root: str,
    volume: str = "",
    chapter_range: str = "",
    clip_watch: str | bool | None = None,
) -> None:
    try:
        from wisdom_workspace import touch_workspace_from_path

        touch_workspace_from_path(novel_root)
    except ImportError:
        pass
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = load_gui_settings()
    data: dict[str, str] = dict(prev)
    data["novel_root"] = novel_root
    if volume.strip():
        data["volume"] = volume.strip()
    if chapter_range.strip():
        data["chapter_range"] = chapter_range.strip()
    if clip_watch is not None:
        if isinstance(clip_watch, bool):
            data["clip_watch"] = "1" if clip_watch else "0"
        else:
            data["clip_watch"] = (
                "1"
                if str(clip_watch).strip().lower() in ("1", "true", "yes", "on")
                else "0"
            )
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
