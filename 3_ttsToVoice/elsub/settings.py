# -*- coding: utf-8 -*-
"""3_ttsToVoice 설정(elsub_config.json) 로드/저장 (실행 파일과 같은 폴더)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIRNAME = "3_ttsToVoice"


def _ensure_wisdom_on_path(from_file: str | Path) -> None:
    for base in [Path.cwd(), *Path(from_file).resolve().parents]:
        if (base / "wisdom_root.py").is_file():
            s = str(base)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise ImportError("wisdom_root.py not found — wisdom 폴더를 워크스페이스 루트로 여세요.")


_ensure_wisdom_on_path(__file__)
from wisdom_root import module_dir, module_output
from wisdom_workspace import (
    folder_dialog_initial,
    get_workspace_dir,
    resolve_module_output,
    touch_workspace_from_path,
    workspace_module_output,
)

CONFIG_FILENAME = "elsub_config.json"
EXAMPLE_FILENAME = "elsub_config.example.json"
GUI_CONFIG_NAME = "elsub_gui_config.json"
OUTPUT_DIRNAME = "output"
INPUT_DIRNAME = "input"


def config_file_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_FILENAME
    return Path(__file__).resolve().parent.parent / CONFIG_FILENAME


def resolve_output_dir() -> Path:
    """``{작업폴더}/3_ttsToVoice/output`` 또는 wisdom 기본."""
    return resolve_module_output(PROJECT_DIRNAME)


def default_input_dir() -> Path:
    """기본 입력: 작업 폴더의 ``2_textToTts/output`` 또는 wisdom ``2_textToTts/output``."""
    ws = get_workspace_dir()
    if ws is not None:
        tts_out = ws / "2_textToTts" / OUTPUT_DIRNAME
        if tts_out.is_dir():
            return tts_out
        return ws
    tts_out = module_dir("2_textToTts") / OUTPUT_DIRNAME
    if tts_out.is_dir():
        return tts_out
    local = module_dir(PROJECT_DIRNAME) / INPUT_DIRNAME
    local.mkdir(parents=True, exist_ok=True)
    return local


def gui_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / GUI_CONFIG_NAME
    return module_dir(PROJECT_DIRNAME) / "dist" / GUI_CONFIG_NAME


def load_gui_settings() -> dict[str, str]:
    p = gui_config_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("input_dir", "output_dir"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()
    return out


def save_gui_settings(*, input_dir: str, output_dir: str) -> None:
    touch_workspace_from_path(input_dir)
    p = gui_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"input_dir": input_dir.strip(), "output_dir": output_dir.strip()}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
