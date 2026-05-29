from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def module_root() -> Path:
    """소스: ``7_utube/`` · frozen exe: ``dist/`` (exe와 같은 폴더)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def config_dir() -> Path:
    d = module_root() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def api_key_path() -> Path:
    return config_dir() / "youtube_api.json"


def load_api_key() -> str:
    """환경변수 ``YOUTUBE_API_KEY`` → ``config/youtube_api.json`` 순."""
    env = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if env:
        return env
    p = api_key_path()
    if not p.is_file():
        return ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        return str(data.get("api_key") or data.get("key") or "").strip()
    return str(data).strip()


def save_api_key(key: str) -> None:
    p = api_key_path()
    p.write_text(json.dumps({"api_key": key.strip()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persist_api_key_if_changed(key: str) -> bool:
    """저장 파일과 다르면 ``youtube_api.json``에 기록. 변경 시 True."""
    k = key.strip()
    if not k or k == load_api_key():
        return False
    save_api_key(k)
    return True
