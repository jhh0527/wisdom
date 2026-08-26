# -*- coding: utf-8 -*-
"""폴더 MP4 → all.mp4 (다수 규격 맞춤 후 고속 concat copy)."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from mp4_merge.ffmpeg_util import (
    concat_copy,
    ffmpeg_bin,
    format_fps,
    format_spec_compact,
    format_spec_short,
    probe_clip_spec,
    probe_duration,
    reencode_to_spec,
    remux_audio_match,
    silent_audio_pad,
    specs_match_for_copy,
)
from mp4_merge.log_util import MergeSessionLog
from mp4_merge.paths import ALL_MP4_NAME, MERGE_LOG_NAME, WORK_DIR_NAME

ProgressFn = Callable[[float, str], None]


def _format_hms(seconds: float) -> str:
    sec = max(0, int(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _pick_majority_spec(clips: list[Path]) -> dict | None:
    """다수 클립의 (해상도·fps·샘플레이트·채널) — 없으면 None."""
    counts: dict[tuple, list[dict]] = {}
    for c in clips:
        spec = probe_clip_spec(c)
        if not spec:
            continue
        key = (
            int(spec["w"]),
            int(spec["h"]),
            spec.get("fps_k"),
            int(spec.get("ar") or 0),
            int(spec.get("ch") or 0),
        )
        counts.setdefault(key, []).append(spec)
    if not counts:
        return None
    best_key = max(counts.items(), key=lambda kv: len(kv[1]))[0]
    # 동일 키면 첫 스펙 사용 (fps float 유지)
    return dict(counts[best_key][0])


def merge_folder_to_all(
    clips: list[Path],
    folder: Path,
    *,
    mute_names: set[str] | None = None,
    cancel_event: threading.Event | None = None,
    on_progress: ProgressFn | None = None,
    on_log: Callable[[str], None] | None = None,
) -> Path:
    """클립을 순서대로 이어 붙여 ``folder/all.mp4``.

    - 기준 규격(다수)과 다른 파일만 재인코딩.
    - 맞춘 뒤 concat ``-c copy`` 무손실 이어붙이기.
    """
    folder = Path(folder)
    clips = [Path(p) for p in clips if Path(p).is_file()]
    if not clips:
        raise ValueError("병합할 MP4가 없습니다.")
    if not ffmpeg_bin():
        raise RuntimeError("ffmpeg 가 필요합니다 (tools/ffmpeg).")

    dest = folder / ALL_MP4_NAME
    work = folder / WORK_DIR_NAME
    work.mkdir(parents=True, exist_ok=True)
    session = MergeSessionLog(folder / MERGE_LOG_NAME, on_line=on_log)
    mute_set = {n.strip().lower() for n in (mute_names or set()) if n and str(n).strip()}
    t0 = time.perf_counter()

    def progress(pct: float, label: str) -> None:
        if on_progress:
            on_progress(min(100.0, max(0.0, pct)), label)

    names = ", ".join(c.name for c in clips)
    session.line("영상합치기를 시작합니다.")
    session.line(f"MP4 {len(clips)}개를 자연순서로 합칩니다: {names}")

    target = _pick_majority_spec(clips)
    if target is None:
        raise RuntimeError("클립 영상 규격을 읽을 수 없습니다.")

    # 음성 없는 다수면 기본 AAC 목표
    if int(target.get("ar") or 0) <= 0:
        target["ar"] = 44100
        target["ch"] = 2
        target["acodec"] = "aac"
    if not target.get("fps") or float(target["fps"]) <= 0:
        target["fps"] = 30.0
        target["fps_k"] = 30.0

    mismatched: list[Path] = []
    for c in clips:
        if c.name.lower() in mute_set:
            continue
        sp = probe_clip_spec(c)
        if sp is None or not specs_match_for_copy(sp, target):
            mismatched.append(c)

    if mismatched:
        session.line(
            "단순 합치기 — 규격이 다른 파일만 본편 규격"
            f"({target['w']}x{target['h']} @{format_fps(target.get('fps'))}fps "
            f"aac {int(target['ar'])}Hz)으로 맞춥니다: "
            + ", ".join(p.name for p in mismatched)
        )
    else:
        session.line("단순 합치기 — 모든 클립이 본편 규격과 일치합니다.")

    session.line(f"기준 규격(다수): {format_spec_short(target)}")

    prepared: list[Path] = []
    n = len(clips)
    for i, c in enumerate(clips, 1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("병합이 중지되었습니다.")
        muted = c.name.lower() in mute_set
        progress(5.0 + 40.0 * (i - 1) / max(1, n), f"준비 {i}/{n}")
        rate = int(target["ar"])
        ch = int(target["ch"])

        if muted:
            out = work / f"_mute_{i:04d}.mp4"
            session.line(f"음소거 패드: {c.name} → {out.name}")
            silent_audio_pad(c, out, sample_rate=rate, channels=ch)
            # 음소거 후 영상 규격도 맞는지 확인
            sp = probe_clip_spec(out)
            if sp is None or not specs_match_for_copy(sp, target):
                out2 = work / f"_mute_norm_{i:04d}.mp4"
                session.line(
                    f"규격 맞춤 재인코딩(이 파일만): {c.name} "
                    f"{format_spec_compact(sp) if sp else '?'} → "
                    f"{format_spec_compact(target)}"
                )
                reencode_to_spec(out, out2, target=target)
                prepared.append(out2)
            else:
                prepared.append(out)
            continue

        sp = probe_clip_spec(c)
        if sp is None or not specs_match_for_copy(sp, target):
            out = work / f"_norm_{i:04d}.mp4"
            before = format_spec_compact(sp) if sp else "?"
            after = format_spec_compact(target)
            session.line(f"규격 맞춤 재인코딩(이 파일만): {c.name} {before} → {after}")
            reencode_to_spec(c, out, target=target)
            prepared.append(out)
            continue

        # 해상도·fps·샘플레이트는 동일 — 코덱만 다를 때 음성만 remux 할 필요는 보통 없음
        # aac가 아니면 copy concat이 깨질 수 있어 음성만 맞춤
        ac = (sp.get("acodec") or "").lower()
        if ac and ac not in {"aac", "mp4a"} and int(sp.get("ar") or 0) > 0:
            out = work / f"_audio_{i:04d}.mp4"
            session.line(f"음성만 remux: {c.name} ({ac} → aac)")
            remux_audio_match(c, out, sample_rate=rate, channels=ch)
            prepared.append(out)
        else:
            prepared.append(c)

    session.line("단순 합치기 — 규격 맞춘 클립으로 무손실 이어붙이기(copy)")
    progress(50.0, "concat copy…")

    def concat_prog(pct: float) -> None:
        progress(50.0 + pct * 0.45, f"병합 {pct:.0f}%")

    try:
        concat_copy(
            prepared,
            dest,
            cancel_event=cancel_event,
            on_progress=concat_prog,
            on_log=session.line,
        )
    except Exception as e:
        session.line(f"[실패] {e}")
        session.line(f"로그 확인: {folder / MERGE_LOG_NAME}")
        raise

    session.line("무손실 빠른 병합 완료")

    # 타임스탬프 (원본 클립 길이 기준)
    session.line("⏱️타임스탬프")
    t_acc = 0.0
    for c in clips:
        session.line(f"{_format_hms(t_acc)} {c.name}")
        d = probe_duration(c) or 0.0
        t_acc += d

    try:
        if work.is_dir():
            shutil.rmtree(work, ignore_errors=True)
    except OSError:
        pass

    elapsed = time.perf_counter() - t0
    size_note = ""
    try:
        mb = dest.stat().st_size / (1024 * 1024)
        if mb >= 1024:
            size_note = f" ({mb / 1024:.2f}G)"
        else:
            size_note = f" ({mb:.0f}MB)"
    except OSError:
        pass
    session.line(
        f"영상 합치기 완료: {dest}{size_note} (소요 시간 {_format_hms(elapsed)})"
    )
    progress(100.0, "완료")
    return dest
