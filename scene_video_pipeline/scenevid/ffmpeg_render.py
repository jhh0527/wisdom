"""장면별 MP4 렌더 + concat → final.mp4."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scenevid.assets import audio_duration_ffprobe
from scenevid.media_paths import ffmpeg_executable
from scenevid.schema import ProjectDoc, Scene


def resolve_ffmpeg_exe() -> str:
    ff = ffmpeg_executable()
    if not ff:
        raise RuntimeError(
            "ffmpeg 를 찾을 수 없습니다. wisdom/tools/ffmpeg/bin 에 두거나 PATH를 설정하세요.\n"
            "https://ffmpeg.org/download.html"
        )
    return ff


def _subtitle_path_filter_arg(srt: Path) -> str:
    """Windows에서 subtitles 필터용 경로 이스케이프."""
    p = srt.resolve().as_posix()
    p = p.replace("\\", "/")
    p = p.replace(":", r"\\:")
    p = p.replace("'", r"'\''")
    return f"subtitles='{p}':charenc=UTF-8"


def render_one_scene(
    scene: Scene,
    root: Path,
    doc: ProjectDoc,
    *,
    burn_subtitles: bool = True,
) -> Path:
    img, mp3, srt = scene.resolved_paths(root)
    out_dir = root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    scene_mp4 = out_dir / f"{scene.id}.mp4"

    if not img.is_file():
        raise FileNotFoundError(f"이미지 없음: {img}")
    if not mp3.is_file():
        raise FileNotFoundError(f"오디오 없음: {mp3}")

    duration = audio_duration_ffprobe(mp3)

    from scenevid.subtitles import write_scene_srt

    if burn_subtitles and scene.narration.strip():
        if not srt.is_file():
            write_scene_srt(srt, scene.narration, duration)
        sub_vf = "," + _subtitle_path_filter_arg(srt)
    else:
        sub_vf = ""

    w, h = doc.settings.width, doc.settings.height
    vf_main = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    vf = vf_main + sub_vf

    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-i",
        str(img.resolve()),
        "-i",
        str(mp3.resolve()),
        "-vf",
        vf,
        "-c:v",
        doc.settings.video_codec,
        "-preset",
        "medium",
        "-crf",
        "20",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        doc.settings.audio_codec,
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(scene_mp4.resolve()),
    ]

    env = dict(os.environ)
    env.setdefault("FONTCONFIG_PATH", "")
    pr = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if pr.returncode != 0:
        raise RuntimeError(f"ffmpeg 장면 실패 [{scene.id}]:\n{pr.stderr}\n{pr.stdout}")
    return scene_mp4


def concat_scenes(scene_mp4s: list[Path], final_out: Path, *, youtube_faststart: bool) -> None:
    if not scene_mp4s:
        raise ValueError("연결할 scene mp4 없음")

    ffmpeg = resolve_ffmpeg_exe()
    if len(scene_mp4s) == 1:
        one = scene_mp4s[0].resolve()
        if youtube_faststart:
            cmd = [ffmpeg, "-y", "-i", str(one), "-movflags", "+faststart", "-c", "copy", str(final_out.resolve())]
            r = subprocess.run(cmd, cwd=str(final_out.parent), capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg faststart 실패:\n{r.stderr}")
        else:
            import shutil as sh

            sh.copy(one, final_out)
        return

    list_path = final_out.parent / "_concat_list.txt"
    lines = []
    for p in scene_mp4s:
        ap = p.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{ap}'")

    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    temp_out = final_out.parent / "_final_nomove.mp4"
    cmd1 = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(temp_out.resolve()),
    ]
    r1 = subprocess.run(cmd1, cwd=str(final_out.parent), capture_output=True, text=True)
    if r1.returncode != 0:
        try:
            list_path.unlink()
        except OSError:
            pass
        raise RuntimeError(f"ffmpeg concat 실패:\n{r1.stderr}")

    try:
        if youtube_faststart:
            cmd2 = [
                ffmpeg,
                "-y",
                "-i",
                str(temp_out),
                "-movflags",
                "+faststart",
                "-c",
                "copy",
                str(final_out.resolve()),
            ]
            r2 = subprocess.run(cmd2, cwd=str(final_out.parent), capture_output=True, text=True)
            if r2.returncode != 0:
                raise RuntimeError(f"ffmpeg faststart 최종 패스 실패:\n{r2.stderr}")
        else:
            import shutil as sh

            if final_out.exists():
                final_out.unlink()
            sh.move(str(temp_out), str(final_out))
    finally:
        if temp_out.exists():
            try:
                temp_out.unlink()
            except OSError:
                pass
        try:
            list_path.unlink()
        except OSError:
            pass


def render_project(
    doc: ProjectDoc,
    root: Path,
    *,
    burn_subtitles: bool = True,
) -> Path:
    """모든 장면 렌더 후 output/final.mp4."""
    clips: list[Path] = []
    for sc in doc.scenes:
        clips.append(render_one_scene(sc, root, doc, burn_subtitles=burn_subtitles))
    final_mp4 = root / "output" / "final.mp4"
    concat_scenes(clips, final_mp4, youtube_faststart=doc.settings.youtube_faststart)
    return final_mp4
