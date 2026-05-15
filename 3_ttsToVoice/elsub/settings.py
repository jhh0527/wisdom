# -*- coding: utf-8 -*-
"""3_ttsToVoice 설정(elsub_config.json) 로드/저장 (실행 파일과 같은 폴더)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


CONFIG_FILENAME = "elsub_config.json"
EXAMPLE_FILENAME = "elsub_config.example.json"
OUTPUT_DIRNAME = "output"
PROJECT_DIRNAME = "3_ttsToVoice"


def config_file_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_FILENAME
    return Path(__file__).resolve().parent.parent / CONFIG_FILENAME


def resolve_output_dir() -> Path:
    """`3_ttsToVoice/output/` 절대 경로를 반환합니다.

    - 동결(exe) 모드: 실행 파일 위치에서 `3_ttsToVoice` 디렉터리를 거슬러 올라가 찾고,
      찾으면 그 하위 `output/`을 사용합니다. 못 찾으면 exe와 같은 폴더의 `output/`.
    - 개발 모드(스크립트): 패키지 부모(`3_ttsToVoice/`) 하위 `output/`을 사용합니다.

    ASCII 경로를 강제해 Windows ffmpeg 의 비ASCII 경로 문제(병합 실패)를 피합니다.
    """
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p / OUTPUT_DIRNAME
    return start / OUTPUT_DIRNAME


def copy_bundled_example_if_needed() -> None:
    """PyInstaller onefile: _MEIPASS에 있는 예시를 exe 옆으로 한 번 복사."""
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    dest_dir = Path(sys.executable).resolve().parent
    dest_example = dest_dir / EXAMPLE_FILENAME
    if dest_example.is_file():
        return
    src = Path(meipass) / EXAMPLE_FILENAME
    if src.is_file():
        try:
            dest_example.write_bytes(src.read_bytes())
        except OSError:
            pass


@dataclass
class AppSettings:
    elevenlabs_api_key: str = ""
    voice_id: str = ""
    model_id: str = "eleven_multilingual_v2"
    default_output_mp3: str = ""


def load_settings() -> AppSettings:
    path = config_file_path()
    if not path.is_file():
        return AppSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(raw, dict):
        return AppSettings()
    return AppSettings(
        elevenlabs_api_key=str(raw.get("elevenlabs_api_key", "") or "").strip(),
        voice_id=str(raw.get("voice_id", "") or "").strip(),
        model_id=str(raw.get("model_id", "") or "eleven_multilingual_v2").strip(),
        default_output_mp3=str(raw.get("default_output_mp3", "") or "").strip(),
    )


def save_settings(s: AppSettings) -> None:
    path = config_file_path()
    data = {
        "elevenlabs_api_key": s.elevenlabs_api_key,
        "voice_id": s.voice_id,
        "model_id": s.model_id or "eleven_multilingual_v2",
        "default_output_mp3": s.default_output_mp3,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def settings_from_vars(
    api_key: str,
    voice_id: str,
    model_id: str,
    default_output_mp3: str,
) -> AppSettings:
    return AppSettings(
        elevenlabs_api_key=api_key.strip(),
        voice_id=voice_id.strip(),
        model_id=model_id.strip() or "eleven_multilingual_v2",
        default_output_mp3=default_output_mp3.strip(),
    )
