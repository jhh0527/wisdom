"""저장소(wisdom) 루트 기준 경로 — 서브프로젝트는 wisdom 폴더 안에만 둔다고 가정."""

from __future__ import annotations

from pathlib import Path

# scenevid/repo_paths.py → parents[2] = wisdom
_WISDOM = Path(__file__).resolve().parents[2]


def wisdom_repo_root() -> Path:
    return _WISDOM


def default_tts_pipeline_root() -> Path:
    return _WISDOM / "tts_audio_pipeline"


def default_tts_python() -> Path | None:
    p = default_tts_pipeline_root() / ".venv_chatterbox" / "Scripts" / "python.exe"
    return p if p.is_file() else None
