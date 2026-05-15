# -*- coding: utf-8 -*-
"""3_ttsToVoice: ElevenLabs TTS HTTP 호출 + MP3 병합(ffmpeg/바이너리)."""

from __future__ import annotations

import http.client
import json
import ssl
from pathlib import Path
from urllib.parse import quote

DEFAULT_HOST = "api.elevenlabs.io"


def strip_tts_tags(text: str) -> str:
    import re

    return re.sub(r"\[[^\]]*\]", "", text)


def synthesize_mp3(
    api_key: str,
    voice_id: str,
    text: str,
    *,
    model_id: str = "eleven_multilingual_v2",
    timeout: int = 120,
) -> bytes:
    plain = strip_tts_tags(text).strip()
    if not plain:
        raise ValueError("합성할 TTS 텍스트가 비어 있습니다.")
    vid = quote(voice_id, safe="-._~")
    path = f"/v1/text-to-speech/{vid}"
    # ensure_ascii=True: 일부 환경에서 HTTP 스택이 본문을 ASCII로 다루는 문제 회피 (API는 \\u 이스케이프 허용)
    payload = json.dumps(
        {"text": plain, "model_id": model_id},
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "audio/mpeg",
        "Content-Length": str(len(payload)),
        "Connection": "close",
    }

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(DEFAULT_HOST, timeout=timeout, context=ctx)
    try:
        conn.request("POST", path, body=payload, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        if resp.status >= 400:
            err = data.decode("utf-8", errors="replace")
            raise RuntimeError(f"ElevenLabs API 오류 {resp.status}: {err}")
        return data
    finally:
        try:
            conn.close()
        except Exception:
            pass


def concat_mp3_files(parts: list[bytes], out_path: str) -> None:
    """바이너리 이어붙이기 (ffmpeg 없을 때 대안)."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as w:
        for blob in parts:
            w.write(blob)


def concat_mp3_files_binary_from_paths(
    segment_paths: list[Path],
    out_path: Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> None:
    """MP3 파일들을 순서대로 바이트 스트림으로 이어붙입니다.

    ffmpeg concat demuxer 가 일부 환경에서 잘못된 단일 구간만 출력하는 경우가 있어,
    `all.mp3` 등 **전체 병합**에는 이 방식을 우선 사용합니다. (동일 인코더 MP3 연속 재생에 적합)
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not segment_paths:
        raise ValueError("병합할 파일이 없습니다.")
    with out_path.open("wb") as w:
        for sp in segment_paths:
            p = Path(sp)
            if not p.is_file():
                raise FileNotFoundError(str(p))
            with p.open("rb") as r:
                while True:
                    chunk = r.read(chunk_size)
                    if not chunk:
                        break
                    w.write(chunk)


def concat_mp3_files_ffmpeg(segment_paths: list[Path], out_path: Path) -> None:
    """ffmpeg concat demuxer로 MP3 파일들을 하나로 병합합니다.

    1차로 `-c copy`(빠름)로 시도하고, 실패하면 `-c:a libmp3lame`로 재인코딩 합니다.
    재인코딩까지 실패하면 RuntimeError 를 올립니다 (상위 호출부에서 바이너리 폴백 처리).
    """
    import subprocess
    import tempfile

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not segment_paths:
        raise ValueError("병합할 세그먼트가 없습니다.")

    out_dir = out_path.parent.resolve()
    lines: list[str] = []
    for sp in segment_paths:
        sp = Path(sp).resolve()
        if not sp.is_file():
            raise FileNotFoundError(str(sp))
        try:
            rel = sp.relative_to(out_dir)
            esc = rel.as_posix().replace("'", "'\\''")
        except ValueError:
            esc = sp.as_posix().replace("'", "'\\''")
        lines.append(f"file '{esc}'")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
        newline="\n",
        dir=str(out_dir),
    ) as tf:
        tf.write("\n".join(lines) + "\n")
        list_path = Path(tf.name)

    def _run(extra_args: list[str]) -> tuple[int, str]:
        r = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                *extra_args,
                str(out_path),
            ],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        return r.returncode, (r.stderr or r.stdout or "").strip()

    try:
        rc, msg = _run(["-c", "copy"])
        if rc != 0:
            rc2, msg2 = _run(["-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100"])
            if rc2 != 0:
                raise RuntimeError(
                    f"ffmpeg 병합 실패 (copy: {msg or 'exit ' + str(rc)} / "
                    f"reencode: {msg2 or 'exit ' + str(rc2)})"
                )
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except OSError:
            pass
