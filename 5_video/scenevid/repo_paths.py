"""저장소(wisdom) 루트 기준 경로 — 서브프로젝트는 wisdom 폴더 안에만 둔다고 가정."""

from __future__ import annotations

from pathlib import Path

# scenevid/repo_paths.py → parents[2] = wisdom
_WISDOM = Path(__file__).resolve().parents[2]


def wisdom_repo_root() -> Path:
    return _WISDOM


def default_scenevid_output_dir() -> Path:
    """videoPG: 자막·음성·이미지 합성 산출물 기본 폴더."""
    return _WISDOM / "5_video" / "output"


def default_tts_voice_output_dir() -> Path:
    """TTS 단계 산출물 (part*.mp3, all.mp3, *.srt 등)."""
    return _WISDOM / "3_ttsToVoice" / "output"


def default_srt_image_output_dir() -> Path:
    """SRT 이미지 단계 산출물 (SRT_NNN.jpg 등)."""
    return _WISDOM / "4_srtToImage" / "output"


def default_scenevid_compose_mp4() -> Path:
    return default_scenevid_output_dir() / "compose_final.mp4"


def pick_default_compose_audio_srt(tts_output: Path | None = None) -> tuple[Path | None, Path | None]:
    """videoPG 기본: ``all.mp3`` / ``all.srt`` 우선, 없으면 ``part01.*``."""
    root = (tts_output or default_tts_voice_output_dir()).resolve()
    all_mp3 = root / "all.mp3"
    all_srt = root / "all.srt"
    if all_mp3.is_file() and all_srt.is_file():
        return all_mp3, all_srt
    p1 = root / "part01.mp3"
    s1 = root / "part01.srt"
    if p1.is_file() and s1.is_file():
        return p1, s1
    mp3s = sorted(root.glob("*.mp3"))
    srts = sorted(root.glob("*.srt"))
    if mp3s and srts:
        return mp3s[0], srts[0]
    return (mp3s[0] if mp3s else None, srts[0] if srts else None)


def default_tts_pipeline_root() -> Path:
    return _WISDOM / "tts_audio_pipeline"


def default_tts_python() -> Path | None:
    p = default_tts_pipeline_root() / ".venv_chatterbox" / "Scripts" / "python.exe"
    return p if p.is_file() else None
