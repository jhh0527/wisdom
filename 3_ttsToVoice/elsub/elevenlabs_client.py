# -*- coding: utf-8 -*-
"""3_ttsToVoice: ElevenLabs TTS HTTP 호출 + MP3 병합(ffmpeg/바이너리)."""

from __future__ import annotations

import http.client
import json
import re
import ssl
from pathlib import Path
from urllib.parse import quote

DEFAULT_HOST = "api.elevenlabs.io"

# 문장부호 없이 이어지는 자막 줄 사이 띄어 읽기 (ElevenLabs SSML)
SUBTITLE_LINE_BREAK = '<break time="0.35s" />'

_BRACKET_TAG_RE = re.compile(r"\[[^\]]*\]", re.IGNORECASE)


def strip_tts_tags(text: str) -> str:
    """길이 추정·SRT용: 대괄호 태그를 제거한 낭독 텍스트."""
    return _BRACKET_TAG_RE.sub("", text)


def prepare_tts_for_api(text: str) -> str:
    """ElevenLabs API용 텍스트. ``[breathes]`` 등은 SSML ``<break>`` 로 변환합니다."""
    s = text.strip()
    s = re.sub(
        r"\[short pause\]\s*\[breathes\]\s*\[continues\]",
        '<break time="1.0s" />',
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\[short pause\]\s*\[breathes\]",
        '<break time="1.0s" />',
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\[short pause\]", '<break time="0.4s" />', s, flags=re.IGNORECASE)
    s = re.sub(r"\[breathes\]", '<break time="0.7s" />', s, flags=re.IGNORECASE)
    s = re.sub(r"\[continues\]", "", s, flags=re.IGNORECASE)
    s = _BRACKET_TAG_RE.sub("", s)
    return s.strip()


def synthesize_mp3(
    api_key: str,
    voice_id: str,
    text: str,
    *,
    model_id: str = "eleven_multilingual_v2",
    timeout: int = 120,
) -> bytes:
    plain = prepare_tts_for_api(text)
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


# ElevenLabs 세그먼트와 동일하게 맞춤 (경계 ID3·DTS 꼬임 방지용 재인코딩)
_FFMPEG_MP3_ENCODE_ARGS = ["-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "1"]


def concat_mp3_files_binary_from_paths(
    segment_paths: list[Path],
    out_path: Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> None:
    """MP3 파일들을 순서대로 바이트 스트림으로 이어붙입니다 (ffmpeg 실패 시 폴백)."""
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


def _write_ffmpeg_concat_list(segment_paths: list[Path], out_path: Path) -> Path:
    """concat demuxer용 filelist.txt 경로를 반환합니다 (호출부에서 삭제)."""
    import tempfile

    out_path = Path(out_path)
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
        return Path(tf.name)


def concat_mp3_files_ffmpeg(segment_paths: list[Path], out_path: Path) -> None:
    """ffmpeg concat + libmp3lame 재인코딩으로 MP3를 병합합니다.

    `-c copy`는 MP3 경계에서 DTS 비단조·중간 ID3로 클릭/길이 어긋남이 날 수 있어
    처음부터 디코드 후 한 번에 인코딩합니다. 실패 시 RuntimeError (상위에서 바이너리 폴백).
    """
    import subprocess
    import sys

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not segment_paths:
        raise ValueError("병합할 세그먼트가 없습니다.")

    list_path = _write_ffmpeg_concat_list(segment_paths, out_path)
    kw: dict = dict(capture_output=True, text=True, timeout=3600)
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    try:
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
                *_FFMPEG_MP3_ENCODE_ARGS,
                str(out_path),
            ],
            **kw,
        )
        if r.returncode != 0:
            msg = (r.stderr or r.stdout or "").strip()
            raise RuntimeError(f"ffmpeg 병합 실패: {msg or 'exit ' + str(r.returncode)}")
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except OSError:
            pass
