"""FFmpeg/ffprobe 래퍼."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ffmpeg_probe_names() -> tuple[str, str]:
    if sys.platform == "win32":
        return ("ffmpeg.exe", "ffprobe.exe")
    return ("ffmpeg", "ffprobe")


def _local_ffmpeg_bin_dir() -> Path | None:
    """wisdom/tools/ffmpeg/bin — Gyan 등에서 ffmpeg·ffprobe 실행 파일만 복사해 두면 PATH 없이 사용."""
    ff_n, fp_n = _ffmpeg_probe_names()
    bases: list[Path] = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).resolve().parent)
    bases.extend(Path(__file__).resolve().parents)
    for base in bases:
        d = base / "tools" / "ffmpeg" / "bin"
        if (d / ff_n).is_file() and (d / fp_n).is_file():
            return d
    return None


def prepend_local_ffmpeg_bin_to_os_path() -> None:
    """로컬 bin이 있으면 PATH 맨 앞에 넣어 `ffmpeg`/`ffprobe` 명령으로도 찾히게 함."""
    d = _local_ffmpeg_bin_dir()
    if d is None:
        return
    ins = str(d.resolve())
    sep = os.pathsep
    cur = os.environ.get("PATH") or (os.environ.get("Path", "") if sys.platform == "win32" else "")
    parts = [p.strip().strip('"') for p in cur.split(sep) if p]
    if ins.lower() not in {p.lower() for p in parts}:
        newp = ins + (sep + cur if cur else "")
        os.environ["PATH"] = newp
        if sys.platform == "win32":
            os.environ["Path"] = newp


def ffmpeg_path() -> str | None:
    ff_n, _ = _ffmpeg_probe_names()
    d = _local_ffmpeg_bin_dir()
    if d is not None:
        return str(d / ff_n)
    return shutil.which("ffmpeg")


def ffprobe_path() -> str | None:
    _, fp_n = _ffmpeg_probe_names()
    d = _local_ffmpeg_bin_dir()
    if d is not None:
        return str(d / fp_n)
    return shutil.which("ffprobe")


def require_ffmpeg() -> str:
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError(
            "FFmpeg 를 찾을 수 없습니다.\n"
            "• (권장) wisdom/tools/ffmpeg/bin 에 ffmpeg.exe·ffprobe.exe 를 두거나\n"
            "• PATH에 FFmpeg 를 추가하세요.\n"
            "https://ffmpeg.org/download.html"
        )
    return ff


def ffprobe_duration_sec(path: Path) -> float:
    fp = ffprobe_path()
    if not fp:
        raise RuntimeError(
            "ffprobe 를 찾을 수 없습니다. wisdom/tools/ffmpeg/bin 또는 FFmpeg PATH를 확인하세요."
        )
    cmd = [
        fp,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffprobe 실패")
    return float((r.stdout or "0").strip())


def run_ffmpeg(args: list[str], *, cwd: Path | None = None) -> str:
    ff = require_ffmpeg()
    cmd = [ff, "-y", *args]
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "ffmpeg 실패").strip())
    return (r.stderr or "").strip()


def trim_video(inp: Path, out: Path, start_sec: float, duration_sec: float | None) -> None:
    """start_sec부터 duration_sec 길이만 자름(duration None이면 끝까지)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if duration_sec is not None and duration_sec <= 0:
        raise ValueError("길이는 0보다 커야 합니다.")
    args = ["-ss", str(max(0.0, start_sec)), "-i", str(inp)]
    if duration_sec is not None:
        args += ["-t", str(duration_sec)]
    args += ["-c", "copy", str(out)]
    run_ffmpeg(args)


def replace_audio_track(video: Path, audio: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out),
    ]
    run_ffmpeg(args)


def extract_audio(video: Path, out_audio: Path) -> None:
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(video), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out_audio)]
    run_ffmpeg(args)


def burn_subtitles(video: Path, srt: Path, out: Path, *, charenc: str = "UTF-8") -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    sp = srt.resolve().as_posix().replace("\\", "/").replace(":", r"\\:").replace("'", r"'\''")
    vf = f"subtitles='{sp}':charenc={charenc}"
    args = ["-i", str(video), "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy", str(out)]
    run_ffmpeg(args)


def concat_videos(paths: list[Path], out: Path, *, copy_codec: bool = True) -> None:
    if len(paths) < 2:
        raise ValueError("영상 파일이 두 개 이상 필요합니다.")
    out.parent.mkdir(parents=True, exist_ok=True)
    list_file = out.parent / "_vs_concat.txt"
    try:
        parts: list[str] = []
        for p in paths:
            raw = str(p.resolve())
            posix = raw.replace("\\", "/")
            esc = posix.replace("'", r"'\''")
            parts.append(f"file '{esc}'")
        list_file.write_text("\n".join(parts) + "\n", encoding="utf-8")
        if copy_codec:
            args = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]
        else:
            args = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c:v", "libx264", "-c:a", "aac", str(out)]
        run_ffmpeg(args)
    finally:
        if list_file.exists():
            try:
                list_file.unlink()
            except OSError:
                pass
