# -*- coding: utf-8 -*-
"""3_ttsToVoice: 원본 자막 + 길이로 SRT 생성.

- `build_srt` / `build_srt_from_durations`: 줄별 길이는 글자 수 추정 또는 실측(ms)을 사용합니다.
- `merge_srt_files`: 파트 SRT 병합 시 `part_mp3_paths` 를 넘기면 오프셋에 ffprobe 길이를 사용합니다.
"""

from __future__ import annotations

import re
from pathlib import Path

from elsub.elevenlabs_client import strip_tts_tags


def estimate_duration_ms(tts_text: str, chars_per_second: float = 11.0, min_ms: int = 800) -> int:
    t = strip_tts_tags(tts_text).strip()
    if not t:
        return min_ms
    sec = max(min_ms / 1000.0, len(t) / chars_per_second)
    return int(sec * 1000)


def ms_to_ts(ms: int) -> str:
    if ms < 0:
        ms = 0
    h, r = divmod(ms, 3600000)
    m, r = divmod(r, 60000)
    s, z = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{z:03d}"


def build_srt(
    entries: list[tuple[str, str]],
    *,
    start_index: int = 1,
    start_ms: int = 0,
) -> tuple[str, int, int]:
    """
    entries: (원본 자막 텍스트, TTS 텍스트) — TTS는 길이 추정에만 사용.

    Returns:
        (SRT 본문, 마지막 다음 자막 인덱스, 마지막 누적 ms)
    """
    durs = [estimate_duration_ms(tts) for _, tts in entries]
    return build_srt_from_durations(
        [(orig, d) for (orig, _), d in zip(entries, durs)],
        start_index=start_index,
        start_ms=start_ms,
    )


def build_srt_from_durations(
    lines: list[tuple[str, int]],
    *,
    start_index: int = 1,
    start_ms: int = 0,
    min_ms: int = 1,
) -> tuple[str, int, int]:
    """원본 자막 + 줄별 길이(ms, 실측 권장)로 SRT 생성.

    lines: (원본 자막 텍스트, duration_ms)
    """
    blocks: list[str] = []
    cur = start_ms
    idx = start_index
    for orig, dur in lines:
        d = max(min_ms, int(dur))
        start = ms_to_ts(cur)
        cur += d
        end = ms_to_ts(cur)
        body = orig.replace("\r\n", "\n").replace("\n", " ").strip()
        blocks.append(f"{idx}\n{start} --> {end}\n{body}\n")
        idx += 1
    body = ("\n".join(blocks) + "\n") if blocks else ""
    return body, idx, cur


def parse_srt_timestamp(ts: str) -> int:
    """`HH:MM:SS,mmm` 또는 `HH:MM:SS.mmm` → 밀리초."""
    ts = ts.strip().replace(".", ",")
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$", ts)
    if not m:
        raise ValueError(f"SRT 타임스탬프 형식이 아닙니다: {ts!r}")
    h, mi, s, z = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return ((h * 60 + mi) * 60 + s) * 1000 + z


def parse_srt_cues(content: str) -> list[tuple[int, int, str]]:
    """SRT 본문을 (start_ms, end_ms, text) 리스트로 파싱합니다."""
    cues: list[tuple[int, int, str]] = []
    raw = content.replace("\r\n", "\n").strip()
    if not raw:
        return cues
    for block in raw.split("\n\n"):
        lines = [ln for ln in block.strip().split("\n") if ln is not None]
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        left, _, right = lines[1].partition("-->")
        try:
            st = parse_srt_timestamp(left)
            en = parse_srt_timestamp(right)
        except ValueError:
            continue
        text = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""
        cues.append((st, en, text))
    return cues


def merge_srt_files(
    part_srt_paths: list[Path],
    *,
    part_mp3_paths: list[Path] | None = None,
) -> tuple[str, int]:
    """part01.srt, part02.srt … 순서로 이어 붙인 SRT 문자열과 마지막 끝 시각(ms)을 반환합니다.

    각 파트 SRT는 0부터 시작하는 타임라인이라고 가정합니다.

    part_mp3_paths 가 같은 길이로 주어지면, 다음 파트 오프셋은 각 파트 SRT의 마지막 큐가 아니라
    해당 MP3의 ffprobe 재생 길이를 사용합니다(구버전 추정 SRT와 실제 음성 길이 불일치 보정).
    """
    from elsub.media_probe import ffprobe_duration_sec

    offset_ms = 0
    out_idx = 1
    chunks: list[str] = []
    use_mp3 = (
        part_mp3_paths is not None
        and len(part_mp3_paths) == len(part_srt_paths)
    )
    for i, path in enumerate(part_srt_paths):
        cues = parse_srt_cues(path.read_text(encoding="utf-8"))
        if cues:
            for st, en, text in cues:
                a = ms_to_ts(st + offset_ms)
                b = ms_to_ts(en + offset_ms)
                chunks.append(f"{out_idx}\n{a} --> {b}\n{text}\n")
                out_idx += 1
        if use_mp3:
            mp = part_mp3_paths[i]  # type: ignore[index]
            try:
                offset_ms += int(round(ffprobe_duration_sec(mp) * 1000))
            except Exception:
                if cues:
                    offset_ms += cues[-1][1]
        elif cues:
            offset_ms += cues[-1][1]
    body = "\n".join(chunks) + ("\n" if chunks else "")
    return body, offset_ms
