# -*- coding: utf-8 -*-
"""PNG → JPEG 변환 및 유튜브·영상 파이프라인용 해상도·용량 최적화."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from png2jpg.naming import extract_first_two_digit_srt_number, extract_srt_number, srt_jpg_name
from png2jpg.srt_match import (
    extract_timestamp_ms_from_stem,
    match_srt_at_timestamp_ms,
    parse_srt_cues,
)

PNG_EXTS = frozenset({".png", ".PNG"})
JPG_EXTS = frozenset({".jpg", ".jpeg", ".JPG", ".JPEG"})

DEFAULT_MAX_WIDTH = 1920
DEFAULT_MAX_HEIGHT = 1080
DEFAULT_JPEG_QUALITY = 88


@dataclass
class ConvertResult:
    source: Path
    output: Path
    srt_number: int
    bytes_before: int
    bytes_after: int
    size_px: tuple[int, int]
    match_note: str = ""

    @property
    def saved_bytes(self) -> int:
        return max(0, self.bytes_before - self.bytes_after)


@dataclass
class ConvertSkip:
    source: Path
    reason: str


def _fit_size(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int]:
    if w <= max_w and h <= max_h:
        return w, h
    scale = min(max_w / w, max_h / h)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    return nw, nh


def _open_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        base = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def convert_one(
    src: Path,
    dst: Path,
    *,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: int = DEFAULT_MAX_HEIGHT,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> ConvertResult:
    if not src.is_file():
        raise FileNotFoundError(src)
    bytes_before = src.stat().st_size

    with Image.open(src) as im:
        im = _open_rgb(im)
        nw, nh = _fit_size(im.width, im.height, max_width, max_height)
        if (nw, nh) != (im.width, im.height):
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)

        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(
            dst,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling=2,
        )

    return ConvertResult(
        source=src.resolve(),
        output=dst.resolve(),
        srt_number=0,
        bytes_before=bytes_before,
        bytes_after=dst.stat().st_size,
        size_px=(nw, nh),
    )


def iter_source_images(
    input_dir: Path,
    *,
    recursive: bool = False,
    include_jpg: bool = False,
) -> list[Path]:
    d = input_dir.resolve()
    if not d.is_dir():
        raise NotADirectoryError(d)

    exts = set(PNG_EXTS)
    if include_jpg:
        exts |= JPG_EXTS

    if recursive:
        files = [p for p in d.rglob("*") if p.is_file() and p.suffix in exts]
    else:
        files = [p for p in d.iterdir() if p.is_file() and p.suffix in exts]
    return sorted(files, key=lambda p: p.name.lower())


def _plan_output_numbers(
    sources: list[Path],
    cues: list[tuple[int, int, int, str]],
) -> list[tuple[Path, int | None, str]]:
    """각 소스 → (경로, SRT번호, 설명). 타임스탬프 파일은 T 순·중복 SRT 미사용."""
    ts_rows: list[tuple[int, Path]] = []
    name_rows: list[tuple[Path, int]] = []
    failures: list[tuple[Path, str]] = []

    for src in sources:
        t_ms = extract_timestamp_ms_from_stem(src.stem)
        if t_ms is not None:
            if cues:
                ts_rows.append((t_ms, src))
            else:
                n_fb = extract_first_two_digit_srt_number(src.stem)
                if n_fb is not None:
                    name_rows.append((src, n_fb))
                else:
                    failures.append((src, "timestamp 파일 — SRT 자막 지정 또는 맨 앞 2자리 숫자 필요"))
            continue
        n = extract_srt_number(src.stem)
        if n is not None:
            name_rows.append((src, n))
        else:
            failures.append((src, "파일명에서 번호를 찾을 수 없음"))

    used: set[int] = set()
    planned: list[tuple[Path, int | None, str]] = []

    for t_ms, src in sorted(ts_rows, key=lambda x: (x[0], x[1].name.lower())):
        mid = match_srt_at_timestamp_ms(cues, t_ms, used)
        if mid is None:
            planned.append((src, None, f"SRT 매칭 실패 T={t_ms/1000:.3f}s"))
            continue
        used.add(mid)
        planned.append((src, mid, f"SRT 매칭 T={t_ms/1000:.3f}s→#{mid}"))

    for src, n in name_rows:
        if n in used:
            planned.append((src, None, f"SRT 번호 {n} 은 타임스탬프 매칭에서 이미 사용됨"))
        else:
            note = "맨 앞 2자리 숫자" if extract_first_two_digit_srt_number(src.stem) == n else "파일명 번호"
            planned.append((src, n, note))

    for src, reason in failures:
        planned.append((src, None, reason))

    return planned


def convert_images(
    input_dir: Path,
    output_dir: Path,
    *,
    srt_path: Path | None = None,
    recursive: bool = False,
    include_jpg: bool = False,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: int = DEFAULT_MAX_HEIGHT,
    quality: int = DEFAULT_JPEG_QUALITY,
    pad_digits: int = 3,
    on_progress: Callable[[int, int, ConvertResult | ConvertSkip], None] | None = None,
) -> tuple[list[ConvertResult], list[ConvertSkip]]:
    sources = iter_source_images(input_dir, recursive=recursive, include_jpg=include_jpg)
    out_dir = output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cues: list[tuple[int, int, int, str]] = []
    if srt_path is not None:
        sp = srt_path.resolve()
        if not sp.is_file():
            raise FileNotFoundError(f"SRT 파일 없음: {sp}")
        cues = parse_srt_cues(sp)

    planned = _plan_output_numbers(sources, cues)
    skipped: list[ConvertSkip] = []
    by_number: dict[int, Path] = {}

    work_items: list[tuple[Path, int, str]] = []
    for src, n, note in planned:
        if n is None:
            skipped.append(ConvertSkip(src, note))
            continue
        if n in by_number:
            skipped.append(ConvertSkip(src, f"SRT_{n:03d} 중복 (이미 {by_number[n].name})"))
            continue
        by_number[n] = src
        work_items.append((src, n, note))

    results: list[ConvertResult] = []
    total = len(work_items)

    for i, (src, n, note) in enumerate(work_items, start=1):
        dst = out_dir / srt_jpg_name(n, pad=pad_digits)
        try:
            r = convert_one(
                src,
                dst,
                max_width=max_width,
                max_height=max_height,
                quality=quality,
            )
            r.srt_number = n
            r.match_note = note
            results.append(r)
            if on_progress:
                on_progress(i, total, r)
        except OSError as e:
            sk = ConvertSkip(src, str(e))
            skipped.append(sk)
            if on_progress:
                on_progress(i, total, sk)

    return results, skipped
