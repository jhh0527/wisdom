"""SRT 타임라인 + 단일 MP3 + 이미지(srt_NN 파일명 ↔ SRT 표시 번호) → 구간별 MP4 후 연결."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from scenevid.assets import audio_duration_ffprobe
from scenevid.compose_overrides import (
    InsertClipSpec,
    default_overrides_path,
    inserts_by_after_cue,
    is_compose_video_path,
    load_compose_overrides,
    per_cue_images_srt_mapping,
    resolved_motion_effects_per_cue,
)
from scenevid.ffmpeg_render import concat_scenes, resolve_ffmpeg_exe, _subtitle_path_filter_arg
from scenevid.subprocess_util import subprocess_run_no_window
from scenevid.motion import (
    build_image_motion_vf,
    compose_motion_span_phase_per_cue,
    effects_for_compose_cues,
    normalize_effect,
)
from scenevid.repo_paths import default_srt_image_output_dir
from scenevid.schema import RenderSettings
from scenevid.srt_image_effects import (
    find_srt_image_effects_json,
    load_cue_effects_from_srt_image_json,
)
from scenevid.srt_parse import load_srt_cues_ms
from scenevid.subtitles import write_single_cue_srt


_MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".mp4"}

ComposeProgressCb = Callable[[int, int, str], None]


def natural_sort_key(path: Path) -> list[str | int]:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def _compose_static_image_input_framerate(duration_sec: float) -> str:
    """정지 이미지+zoompan 클립당 입력 프레임 수를 ~1로 유지하기 위한 프레임레이트.

    ``-loop 1`` + 높은 ``-framerate`` 이면 zoompan 이 입력 프레임마다 사이클을 재시작하여
    장시간 재생 시 모션이 리셋·떨림처럼 보입니다. ``1/duration`` Hz 로 두면 한 클립당 입력이
    거의 한 장이라 한 사이클로 부드럽게 이어집니다.
    """
    dur = max(float(duration_sec), 1e-6)
    rate = 1.0 / dur
    s = f"{rate:.12f}".rstrip("0").rstrip(".")
    return s if s else "1"


def clamp_cues_ms_to_audio(
    cues: list[tuple[int, int, int, str]],
    audio_duration_sec: float,
) -> tuple[list[tuple[int, int, int, str]], str]:
    """SRT 큐 종료 시각을 MP3 재생 길이 안으로 자릅니다. (MP4만 길어지는 현상 방지)"""
    audio_ms = max(0, int(round(float(audio_duration_sec) * 1000.0)))
    warn = ""
    if cues:
        last_end = max(c[2] for c in cues)
        if last_end > audio_ms + 80:
            warn = (
                f"SRT 끝({last_end / 60000:.2f}분)이 MP3({audio_ms / 60000:.2f}분)보다 깁니다. "
                "MP3 길이로 자막 구간을 잘랐습니다."
            )
    out: list[tuple[int, int, int, str]] = []
    for mid, t0, t1, txt in cues:
        if audio_ms <= 0:
            break
        if t0 >= audio_ms:
            continue
        end = min(int(t1), audio_ms)
        if end <= int(t0):
            continue
        out.append((mid, int(t0), end, txt))
    return out, warn


def list_compose_images(images_dir: Path) -> list[Path]:
    if not images_dir.is_dir():
        return []
    files = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in _MEDIA_EXT]
    return sorted(files, key=natural_sort_key)


def default_compose_audio(assets: Path) -> Path | None:
    part = [p for p in assets.glob("part*.mp3") if p.is_file()]
    if part:
        return sorted(part, key=natural_sort_key)[0]
    mp3s = [p for p in assets.glob("*.mp3") if p.is_file()]
    return sorted(mp3s, key=natural_sort_key)[0] if mp3s else None


def default_compose_srt(assets: Path, audio: Path | None) -> Path | None:
    if audio is not None:
        cand = assets / f"{audio.stem}.srt"
        if cand.is_file():
            return cand
    part = [p for p in assets.glob("part*.srt") if p.is_file()]
    if part:
        return sorted(part, key=natural_sort_key)[0]
    srts = [p for p in assets.glob("*.srt") if p.is_file()]
    return sorted(srts, key=natural_sort_key)[0] if srts else None


def _compose_video_vf(
    w: int,
    h: int,
    fps: int,
    duration_sec: float,
    effect: str,
    srt: Path | None,
    *,
    burn_subtitles: bool,
    subtitle_cwd: Path | None = None,
    motion_span_sec: float | None = None,
    motion_phase_sec: float | None = None,
) -> str:
    base = build_image_motion_vf(
        w,
        h,
        fps,
        duration_sec,
        effect,
        motion_span_sec=motion_span_sec,
        motion_phase_sec=motion_phase_sec,
    )
    if burn_subtitles and srt is not None:
        return base + "," + _subtitle_path_filter_arg(srt, ffmpeg_cwd=subtitle_cwd)
    return base


def render_compose_black_clip(
    *,
    audio: Path,
    start_sec: float,
    end_sec: float,
    cue_text: str,
    out_mp4: Path,
    settings: RenderSettings,
    burn_subtitles: bool,
    work_srt: Path,
) -> None:
    """이미지 삭제(검은 화면) 구간 — 원본 MP3 구간만 유지."""
    dur = max(0.06, float(end_sec) - float(start_sec))
    st = max(0.0, float(start_sec))
    en = float(end_sec)
    w, h, fps = settings.width, settings.height, settings.fps

    if burn_subtitles and (cue_text or "").strip():
        write_single_cue_srt(work_srt, cue_text, dur)
        vf = f"format=yuv420p,{_subtitle_path_filter_arg(work_srt, ffmpeg_cwd=out_mp4.parent)}"
    else:
        vf = "format=yuv420p"

    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={w}x{h}:r={fps}:d={dur}",
        "-i",
        str(audio.resolve()),
        "-vf",
        vf,
        "-af",
        f"atrim=start={st}:end={en},asetpts=PTS-STARTPTS",
        "-c:v",
        settings.video_codec,
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(fps),
        "-keyint_min",
        str(fps),
        "-sc_threshold",
        "0",
        "-c:a",
        settings.audio_codec,
        "-b:a",
        "192k",
        "-shortest",
        "-r",
        str(fps),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(out_mp4.resolve()),
    ]
    env = dict(os.environ)
    env.setdefault("FONTCONFIG_PATH", "")
    pr = subprocess_run_no_window(
        cmd,
        cwd=str(out_mp4.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if pr.returncode != 0:
        raise RuntimeError(f"ffmpeg 검은 클립 실패:\n{pr.stderr}\n{pr.stdout}")


def render_compose_insert_clip(
    *,
    image: Path,
    duration_sec: float,
    subtitle_text: str,
    out_mp4: Path,
    settings: RenderSettings,
    burn_subtitles: bool,
    work_srt: Path,
    effect: str,
) -> None:
    """삽입 구간 — 무음 + 정지 이미지(선택 자막)."""
    dur = max(0.06, float(duration_sec))
    eff = normalize_effect(effect)

    if burn_subtitles and (subtitle_text or "").strip():
        write_single_cue_srt(work_srt, subtitle_text, dur)
        vf = _compose_video_vf(
            settings.width,
            settings.height,
            settings.fps,
            dur,
            eff,
            work_srt,
            burn_subtitles=True,
            subtitle_cwd=out_mp4.parent,
        )
    else:
        vf = _compose_video_vf(
            settings.width,
            settings.height,
            settings.fps,
            dur,
            eff,
            None,
            burn_subtitles=False,
        )

    input_fps = _compose_static_image_input_framerate(dur) if eff != "none" else str(settings.fps)

    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        input_fps,
        "-loop",
        "1",
        "-i",
        str(image.resolve()),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf",
        vf,
        "-t",
        str(dur),
        "-c:v",
        settings.video_codec,
        "-preset",
        "medium",
        "-crf",
        "20",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(settings.fps),
        "-keyint_min",
        str(settings.fps),
        "-sc_threshold",
        "0",
        "-c:a",
        settings.audio_codec,
        "-b:a",
        "192k",
        "-r",
        str(settings.fps),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(out_mp4.resolve()),
    ]
    env = dict(os.environ)
    env.setdefault("FONTCONFIG_PATH", "")
    pr = subprocess_run_no_window(
        cmd,
        cwd=str(out_mp4.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if pr.returncode != 0:
        raise RuntimeError(f"ffmpeg 삽입 클립 실패:\n{pr.stderr}\n{pr.stdout}")


def _compose_scale_pad_vf(w: int, h: int) -> str:
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )


def render_compose_video_clip(
    *,
    video: Path,
    audio: Path,
    start_sec: float,
    end_sec: float,
    cue_text: str,
    out_mp4: Path,
    settings: RenderSettings,
    burn_subtitles: bool,
    work_srt: Path,
) -> None:
    """MP4 B-roll — Ken Burns 없음, 영상 내장 오디오는 사용하지 않음 (MP3만).

    짧은 MP4가 SRT 구간보다 먼저 끝나지 않도록 루프·trim 으로 영상 길이를 오디오 구간과 맞춥니다.
    """
    dur = max(0.06, float(end_sec) - float(start_sec))
    st = max(0.0, float(start_sec))
    en = float(end_sec)
    w, h, fps = settings.width, settings.height, settings.fps

    scale_pad = _compose_scale_pad_vf(w, h)
    if burn_subtitles:
        write_single_cue_srt(work_srt, cue_text, dur)
        sub = _subtitle_path_filter_arg(work_srt, ffmpeg_cwd=out_mp4.parent)
        vchain = f"{scale_pad},{sub},trim=duration={dur:.6f},setpts=PTS-STARTPTS"
    else:
        vchain = f"{scale_pad},trim=duration={dur:.6f},setpts=PTS-STARTPTS"

    fc = (
        f"[0:v]fps={fps},{vchain}[v];"
        f"[1:a]atrim=start={st:.6f}:end={en:.6f},asetpts=PTS-STARTPTS[a]"
    )

    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(video.resolve()),
        "-i",
        str(audio.resolve()),
        "-filter_complex",
        fc,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        str(dur),
        "-c:v",
        settings.video_codec,
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(fps),
        "-keyint_min",
        str(fps),
        "-sc_threshold",
        "0",
        "-c:a",
        settings.audio_codec,
        "-b:a",
        "192k",
        "-r",
        str(fps),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(out_mp4.resolve()),
    ]
    env = dict(os.environ)
    env.setdefault("FONTCONFIG_PATH", "")
    pr = subprocess_run_no_window(
        cmd,
        cwd=str(out_mp4.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if pr.returncode != 0:
        raise RuntimeError(f"ffmpeg 영상 클립 실패:\n{pr.stderr}\n{pr.stdout}")


def render_compose_clip(
    *,
    image: Path,
    audio: Path,
    start_sec: float,
    end_sec: float,
    cue_text: str,
    out_mp4: Path,
    settings: RenderSettings,
    burn_subtitles: bool,
    work_srt: Path,
    effect: str = "none",
    motion_span_sec: float | None = None,
    motion_phase_sec: float | None = None,
) -> None:
    if is_compose_video_path(image):
        render_compose_video_clip(
            video=image,
            audio=audio,
            start_sec=start_sec,
            end_sec=end_sec,
            cue_text=cue_text,
            out_mp4=out_mp4,
            settings=settings,
            burn_subtitles=burn_subtitles,
            work_srt=work_srt,
        )
        return
    dur = max(0.06, float(end_sec) - float(start_sec))
    st = max(0.0, float(start_sec))
    en = float(end_sec)
    eff_norm = normalize_effect(effect)
    input_fps = _compose_static_image_input_framerate(dur) if eff_norm != "none" else str(settings.fps)

    if burn_subtitles:
        write_single_cue_srt(work_srt, cue_text, dur)
        vf = _compose_video_vf(
            settings.width,
            settings.height,
            settings.fps,
            dur,
            effect,
            work_srt,
            burn_subtitles=True,
            subtitle_cwd=out_mp4.parent,
            motion_span_sec=motion_span_sec,
            motion_phase_sec=motion_phase_sec,
        )
    else:
        vf = _compose_video_vf(
            settings.width,
            settings.height,
            settings.fps,
            dur,
            effect,
            None,
            burn_subtitles=False,
            motion_span_sec=motion_span_sec,
            motion_phase_sec=motion_phase_sec,
        )

    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        input_fps,
        "-loop",
        "1",
        "-i",
        str(image.resolve()),
        "-i",
        str(audio.resolve()),
        "-vf",
        vf,
        "-af",
        f"atrim=start={st}:end={en},asetpts=PTS-STARTPTS",
        "-t",
        str(dur),
        "-c:v",
        settings.video_codec,
        "-preset",
        "medium",
        "-crf",
        "20",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(settings.fps),
        "-keyint_min",
        str(settings.fps),
        "-sc_threshold",
        "0",
        "-c:a",
        settings.audio_codec,
        "-b:a",
        "192k",
        "-r",
        str(settings.fps),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(out_mp4.resolve()),
    ]
    env = dict(os.environ)
    env.setdefault("FONTCONFIG_PATH", "")
    pr = subprocess_run_no_window(
        cmd,
        cwd=str(out_mp4.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if pr.returncode != 0:
        raise RuntimeError(f"ffmpeg compose 클립 실패:\n{pr.stderr}\n{pr.stdout}")


def render_compose_from_assets(
    *,
    audio_mp3: Path,
    srt_path: Path,
    images_dir: Path,
    out_mp4: Path,
    settings: RenderSettings | None = None,
    burn_subtitles: bool = True,
    default_effect: str = "none",
    effects_file: Path | None = None,
    assets_root: Path | None = None,
    overrides_path: Path | None = None,
    override_cue_images: dict[int, Path | None] | None = None,
    override_inserts: list[InsertClipSpec] | None = None,
    override_cue_effects: dict[int, str] | None = None,
    override_image_effects: dict[str, str] | None = None,
    progress: ComposeProgressCb | None = None,
) -> Path:
    """part01.srt 큐별 이미지 합성. 이미지는 ``images/SRT_NNN.*`` 번호 ≤ SRT 표시 번호 중 최대 번호로 매칭하고,
    해당 파일이 없으면 직전 구간 이미지를 유지합니다. JSON·GUI의 cue_images로 교체·검정 가능.
    ``compose_overrides.json`` 의 ``cue_effects``·``image_effects``(또는 override)로 효과를 지정할 수 있습니다.
    같은 정지 이미지가 연속된 SRT 큐에 걸쳐 있으면 줌/팬 효과는 그 연속 구간 전체에 대해 한 번만 재생되며,
    각 클립은 그 타임라인의 일부만 잘라 씁니다(큐마다 효과가 처음부터 반복되지 않음).
    우선순위: 큐별 ``cue_effects`` → (이전 큐와 같은 이미지면 이전 큐에 적용된 효과 유지) → ``image_effects`` → ``compose_effects.txt``/기본값."""
    if not audio_mp3.is_file():
        raise FileNotFoundError(f"오디오 없음: {audio_mp3}")
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT 없음: {srt_path}")

    cues = load_srt_cues_ms(srt_path)
    if not cues:
        raise ValueError(f"SRT에 큐가 없습니다: {srt_path}")

    audio_sec = audio_duration_ffprobe(audio_mp3)
    cues, clamp_warn = clamp_cues_ms_to_audio(cues, audio_sec)
    if not cues:
        raise ValueError(
            "MP3 재생 길이를 넘는 자막만 있거나 자른 뒤 유효한 큐가 없습니다. 오디오와 SRT 타임코드를 확인하세요."
        )

    root = (assets_root or images_dir.parent).resolve()

    def _resolve_overrides_file(explicit: Path | None) -> Path | None:
        if explicit is not None:
            p = explicit.resolve()
            if not p.is_file():
                raise FileNotFoundError(f"overrides 파일 없음: {p}")
            return p
        cand = default_overrides_path(root)
        return cand if cand.is_file() else None

    ov_file = _resolve_overrides_file(overrides_path)
    if override_cue_images is not None and override_inserts is not None:
        overrides = dict(override_cue_images)
        inserts = list(override_inserts)
        _, _, cue_fx_disk, img_fx_disk = load_compose_overrides(ov_file, root)
    elif override_cue_images is not None or override_inserts is not None:
        raise ValueError("override_cue_images 와 override_inserts 는 둘 다 지정하거나 둘 다 생략하세요.")
    else:
        overrides, inserts, cue_fx_disk, img_fx_disk = load_compose_overrides(ov_file, root)

    json_fx: dict[int, str] = {}
    json_path = find_srt_image_effects_json(images_dir, root, default_srt_image_output_dir())
    if json_path:
        try:
            json_fx = load_cue_effects_from_srt_image_json(json_path)
        except (OSError, ValueError):
            json_fx = {}

    cue_fx_merged = {**json_fx, **dict(cue_fx_disk)}
    if override_cue_effects:
        cue_fx_merged.update(override_cue_effects)

    img_fx_merged = dict(img_fx_disk)
    if override_image_effects:
        img_fx_merged.update(override_image_effects)

    ins_by = inserts_by_after_cue(inserts)

    for idx, p in overrides.items():
        if p is not None and not p.is_file():
            raise FileNotFoundError(f"cue_images[{idx}] 파일 없음: {p}")
    for ins in inserts:
        if not ins.image.is_file():
            raise FileNotFoundError(f"삽입 이미지 없음: {ins.image}")

    n_cues = len(cues)
    map_ids = [c[0] for c in cues]
    resolved_imgs = per_cue_images_srt_mapping(map_ids, images_dir, overrides)

    stg = settings or RenderSettings()
    work = out_mp4.parent / "_compose_work"
    work.mkdir(parents=True, exist_ok=True)

    eff_list_cue = effects_for_compose_cues(
        n_cues,
        effects_file=effects_file,
        images_dir=images_dir,
        default_effect=default_effect,
    )
    motion_per_cue = resolved_motion_effects_per_cue(
        map_ids, resolved_imgs, cue_fx_merged, img_fx_merged, eff_list_cue
    )
    span_phase_per_cue = compose_motion_span_phase_per_cue(cues, resolved_imgs)

    clip_seq = 0
    clips: list[Path] = []

    total_steps = len(ins_by.get(0, []))
    for ci in range(1, n_cues + 1):
        total_steps += 1 + len(ins_by.get(ci, []))
    total_steps += 1  # concat

    done = 0

    def prog(msg: str) -> None:
        if progress:
            progress(done, total_steps, msg)

    prog(clamp_warn if clamp_warn else "합성 준비…")

    def _next_paths() -> tuple[Path, Path]:
        nonlocal clip_seq
        clip_seq += 1
        return work / f"compose_{clip_seq:04d}.mp4", work / f"compose_{clip_seq:04d}.srt"

    try:
        for ins in ins_by.get(0, []):
            mp, sr = _next_paths()
            render_compose_insert_clip(
                image=ins.image,
                duration_sec=ins.duration_sec,
                subtitle_text=ins.subtitle,
                out_mp4=mp,
                settings=stg,
                burn_subtitles=burn_subtitles,
                work_srt=sr,
                effect=ins.effect,
            )
            clips.append(mp)
            done += 1
            prog(f"삽입 클립 완료 ({done}/{total_steps})")

        for cue_i in range(1, n_cues + 1):
            _map_id, t0, t1, text = cues[cue_i - 1]
            st_s = t0 / 1000.0
            en_s = t1 / 1000.0
            mp, sr = _next_paths()
            img_e = resolved_imgs[cue_i - 1]
            eff = motion_per_cue[cue_i - 1]
            mspan, mphase = span_phase_per_cue[cue_i - 1]
            if img_e is None:
                render_compose_black_clip(
                    audio=audio_mp3,
                    start_sec=st_s,
                    end_sec=en_s,
                    cue_text=text,
                    out_mp4=mp,
                    settings=stg,
                    burn_subtitles=burn_subtitles,
                    work_srt=sr,
                )
            else:
                render_compose_clip(
                    image=img_e,
                    audio=audio_mp3,
                    start_sec=st_s,
                    end_sec=en_s,
                    cue_text=text,
                    out_mp4=mp,
                    settings=stg,
                    burn_subtitles=burn_subtitles,
                    work_srt=sr,
                    effect=eff,
                    motion_span_sec=mspan,
                    motion_phase_sec=mphase,
                )
            clips.append(mp)
            done += 1
            prog(f"SRT 큐 {cue_i}/{n_cues} 완료 ({done}/{total_steps})")

            for ins in ins_by.get(cue_i, []):
                mp2, sr2 = _next_paths()
                render_compose_insert_clip(
                    image=ins.image,
                    duration_sec=ins.duration_sec,
                    subtitle_text=ins.subtitle,
                    out_mp4=mp2,
                    settings=stg,
                    burn_subtitles=burn_subtitles,
                    work_srt=sr2,
                    effect=ins.effect,
                )
                clips.append(mp2)
                done += 1
                prog(f"삽입 클립 완료 ({done}/{total_steps})")

        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        prog(f"세그먼트 연결 중… ({done}/{total_steps})")
        concat_scenes(clips, out_mp4, youtube_faststart=stg.youtube_faststart)
        done += 1
    finally:
        for p in work.glob("compose_*.mp4"):
            try:
                p.unlink()
            except OSError:
                pass
        for p in work.glob("compose_*.srt"):
            try:
                p.unlink()
            except OSError:
                pass

    return out_mp4
