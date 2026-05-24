"""저장소(wisdom) 루트 기준 경로 — 소스·PyInstaller exe 모두 ``intellij/wisdom`` 을 찾습니다."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path


def _looks_like_wisdom_root(p: Path) -> bool:
    try:
        r = p.resolve()
    except OSError:
        return False
    return (
        (r / "5_video").is_dir()
        and (r / "3_ttsToVoice").is_dir()
        and (r / "4_srtToImage").is_dir()
    )


def _resolve_wisdom_root() -> Path:
    """videoPG 기본 경로용 wisdom 루트.

    - 환경 변수 ``WISDOM_ROOT``
    - frozen: ``5_video/dist/*.exe`` → 상위가 ``5_video`` → 그 상위가 wisdom
    - 소스: ``scenevid/repo_paths.py`` 기준 ``parents[2]``
    - 위가 실패하면 후보 경로에서 상위로 올라가며 탐색
    """
    env = os.environ.get("WISDOM_ROOT", "").strip()
    if env:
        cand = Path(env).expanduser()
        if _looks_like_wisdom_root(cand):
            return cand.resolve()

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        candidates.extend([exe.parent, exe.parent.parent, exe.parent.parent.parent])
    here = Path(__file__).resolve()
    if len(here.parents) >= 3:
        candidates.append(here.parents[2])
    candidates.append(Path.cwd())

    seen: set[str] = set()
    for start in candidates:
        key = str(start)
        if key in seen:
            continue
        seen.add(key)
        p = start
        for _ in range(8):
            if _looks_like_wisdom_root(p):
                return p.resolve()
            parent = p.parent
            if parent == p:
                break
            p = parent

    if len(here.parents) >= 3:
        return here.parents[2].resolve()
    return here.resolve()


_WISDOM = _resolve_wisdom_root()


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


def default_scenevid_compose_mp4_name() -> str:
    """videoPG: 합성 MP4 기본 파일명 ``yyyymmdd.mp4``."""
    return f"{date.today():%Y%m%d}.mp4"


def default_scenevid_compose_mp4() -> Path:
    return default_scenevid_output_dir() / default_scenevid_compose_mp4_name()


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
