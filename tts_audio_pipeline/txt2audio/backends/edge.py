"""Microsoft Edge 온라인 TTS(edge-tts). API 키 불필요."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import edge_tts

from txt2audio.audio_merge import concat_mp3_binary, try_concat_with_ffmpeg
from txt2audio.backends.base import SynthesisBackend
from txt2audio.chunking import split_for_tts


class EdgeTtsBackend(SynthesisBackend):
    """edge-tts 기반 합성. 한국어 기본 음성: ko-KR-SunHiNeural."""

    def __init__(
        self,
        voice: str,
        *,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        max_chars_per_request: int = 2800,
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.max_chars = max_chars_per_request

    async def synthesize_file(
        self,
        text: str,
        output_path: Path,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        def rep(done: int, total: int) -> None:
            if on_progress is not None and total > 0:
                on_progress(done, total)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pieces = split_for_tts(text, self.max_chars)
        if not pieces:
            raise ValueError("합성할 텍스트가 비어 있습니다.")

        n = len(pieces)
        total_steps = n + (1 if n > 1 else 0)
        rep(0, total_steps)

        if n == 1:
            comm = edge_tts.Communicate(
                pieces[0],
                self.voice,
                rate=self.rate,
                pitch=self.pitch,
                volume=self.volume,
            )
            await comm.save(str(output_path))
            rep(1, total_steps)
            return

        tmp_paths: list[Path] = []
        try:
            for i, chunk in enumerate(pieces):
                tmp = output_path.with_suffix(f".part{i:04d}{output_path.suffix}")
                comm = edge_tts.Communicate(
                    chunk,
                    self.voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    volume=self.volume,
                )
                await comm.save(str(tmp))
                tmp_paths.append(tmp)
                rep(i + 1, total_steps)

            if await try_concat_with_ffmpeg(tmp_paths, output_path):
                rep(total_steps, total_steps)
                return
            if output_path.suffix.lower() == ".mp3":
                concat_mp3_binary(tmp_paths, output_path)
                rep(total_steps, total_steps)
                return
            raise RuntimeError(
                "여러 구간으로 나뉜 합성입니다. 이어붙이려면 ffmpeg를 설치하거나 "
                "출력 확장자를 .mp3로 지정하세요."
            )
        finally:
            for p in tmp_paths:
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass


async def list_voices(language_prefix: str | None = None) -> list[dict[str, str]]:
    """edge-tts 음성 목록. language_prefix 예: ko, en."""
    voices = await edge_tts.list_voices()
    rows: list[dict[str, str]] = []
    for v in voices:
        short = v.get("ShortName", "")
        locale = v.get("Locale", "")
        friendly = v.get("FriendlyName", "")
        if language_prefix and not locale.lower().startswith(language_prefix.lower() + "-"):
            continue
        rows.append({"ShortName": short, "Locale": locale, "FriendlyName": friendly})
    rows.sort(key=lambda r: (r["Locale"], r["ShortName"]))
    return rows
