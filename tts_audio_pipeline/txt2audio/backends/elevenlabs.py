"""ElevenLabs REST API(선택). 환경 변수 ELEVENLABS_API_KEY 필요."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
import urllib.error
import urllib.request
from pathlib import Path

from txt2audio.audio_merge import concat_mp3_binary, try_concat_with_ffmpeg
from txt2audio.backends.base import SynthesisBackend
from txt2audio.chunking import split_for_tts


class ElevenLabsBackend(SynthesisBackend):
    """model_id 기본값: eleven_multilingual_v2."""

    def __init__(
        self,
        voice_id: str,
        *,
        model_id: str = "eleven_multilingual_v2",
        max_chars_per_request: int = 4500,
    ) -> None:
        self.voice_id = voice_id
        self.model_id = model_id
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

        key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not key:
            raise RuntimeError("환경 변수 ELEVENLABS_API_KEY가 설정되어 있지 않습니다.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pieces = split_for_tts(text, self.max_chars)
        if not pieces:
            raise ValueError("합성할 텍스트가 비어 있습니다.")

        n = len(pieces)
        total_steps = n + (1 if n > 1 else 0)
        rep(0, total_steps)

        if n == 1:
            data = await asyncio.to_thread(_post_tts, key, self.voice_id, self.model_id, pieces[0])
            output_path.write_bytes(data)
            rep(1, total_steps)
            return

        tmp_paths: list[Path] = []
        try:
            for i, chunk in enumerate(pieces):
                data = await asyncio.to_thread(_post_tts, key, self.voice_id, self.model_id, chunk)
                tmp = output_path.with_suffix(f".part{i:04d}{output_path.suffix}")
                tmp.write_bytes(data)
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
                "여러 구간 합성: ffmpeg 설치 또는 출력을 .mp3로 지정해 이어붙이세요."
            )
        finally:
            for p in tmp_paths:
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass


def _post_tts(api_key: str, voice_id: str, model_id: str, text: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = json.dumps(
        {
            "text": text,
            "model_id": model_id,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs API 오류 {e.code}: {err}") from e
