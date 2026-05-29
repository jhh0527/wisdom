"""여러 오디오 조각을 하나의 파일로 합칩니다."""

from __future__ import annotations

import asyncio
from pathlib import Path


async def try_concat_with_ffmpeg(parts: list[Path], out: Path) -> bool:
    import shutil

    if shutil.which("ffmpeg") is None or not parts:
        return False

    list_file = out.with_suffix(".concat.txt")
    try:
        lines = "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts)
        list_file.write_text(lines, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        code = await proc.wait()
        return code == 0 and out.exists()
    except OSError:
        return False
    finally:
        if list_file.exists():
            try:
                list_file.unlink()
            except OSError:
                pass


def concat_mp3_binary(parts: list[Path], out: Path) -> None:
    with out.open("wb") as w:
        for p in parts:
            w.write(p.read_bytes())
