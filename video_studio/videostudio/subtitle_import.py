"""TXT·Markdown·JSON 등에서 SRT 문자열 생성."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def format_srt_timestamp(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    whole = int(s)
    ms = int(round((s - whole) * 1000))
    if ms >= 1000:
        whole += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{whole:02d},{ms:03d}"


def build_srt(cues: list[tuple[float, float, str]]) -> str:
    lines: list[str] = []
    idx = 0
    for a, b, text in cues:
        text = str(text).strip()
        if not text:
            continue
        idx += 1
        if b <= a:
            b = a + max(0.25, min(45.0, len(text) * 0.1))
        lines.append(f"{idx}\n{format_srt_timestamp(a)} --> {format_srt_timestamp(b)}\n{text}\n")
    return "\n".join(lines) + ("\n" if lines else "")


def _split_text_plain(raw: str) -> list[str]:
    raw = raw.replace("\r\n", "\n").strip()
    if not raw:
        return []
    parts = re.split(r"\n\s*\n+", raw)
    blocks = [p.strip() for p in parts if p.strip()]
    if len(blocks) == 1 and "\n" in blocks[0]:
        line_blocks = [ln.strip() for ln in blocks[0].split("\n") if ln.strip()]
        return line_blocks if line_blocks else blocks
    return blocks


def _normalize_md_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\s*\d+\.\s+", "", line)
    line = line.removeprefix("*").removeprefix("-").strip()
    line = line.replace("`", "").replace("**", "")
    return line


def _split_markdown(raw: str) -> list[str]:
    raw = raw.replace("\r\n", "\n")
    raw = re.sub(r"^#{1,6}\s*[^\n]*\n", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n---+ *\n+", "\n\n", raw)

    segments: list[str] = []
    buf: list[str] = []
    for p in _split_text_plain(raw):
        for ln in p.split("\n"):
            ln = ln.strip()
            if not ln or ln.startswith("```"):
                continue
            if re.match(r"^@image\s*:", ln) or ln.startswith("!["):
                if buf:
                    segments.append("\n".join(buf))
                    buf = []
                continue
            ln2 = _normalize_md_line(ln)
            if ln2:
                buf.append(ln2)
        if buf:
            segments.append("\n".join(buf))
            buf = []

    out: list[str] = []
    for b in segments:
        b = b.strip()
        if b and (not out or out[-1] != b):
            out.append(b)
    return out


def _text_from_entry(item: dict[str, Any]) -> str | None:
    if not isinstance(item, dict):
        return None
    for k in ("text", "content", "line", "value", "body", "narration", "subtitle"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _timing_from_segment(seg: dict[str, Any]) -> tuple[float, float] | None:
    """Whisper 호환 세그먼트: start/end(초)."""
    t0 = seg.get("start")
    t1 = seg.get("end")
    if isinstance(t0, (int, float)):
        tt0 = float(t0)
        if isinstance(t1, (int, float)) and float(t1) > tt0:
            return tt0, float(t1)
        dur = seg.get("duration")
        if isinstance(dur, (int, float)) and float(dur) > 0:
            return tt0, tt0 + float(dur)
    seek = seg.get("seek")
    if isinstance(seek, (int, float)) and isinstance(seg.get("end"), (int, float)):
        return float(seek), float(seg["end"])
    return None


def cues_from_segments_list(segments: list[Any]) -> list[tuple[float, float, str]] | None:
    cues: list[tuple[float, float, str]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        tim = _timing_from_segment(seg)
        txt = _text_from_entry(seg) or seg.get("text")
        if txt is None and isinstance(seg.get("tokens"), list):
            txt = "".join(str(t) for t in seg["tokens"] if t).strip()
        txt = str(txt).strip() if txt is not None else ""
        if not txt:
            continue
        if tim:
            a, b = tim
            if b <= a:
                b = a + 0.5
            cues.append((a, b, txt))
    if not cues:
        return None
    cues.sort(key=lambda x: x[0])
    return cues


def extract_timed_cues(data: Any) -> list[tuple[float, float, str]] | None:
    if isinstance(data, dict):
        if "segments" in data and isinstance(data["segments"], list):
            r = cues_from_segments_list(data["segments"])
            if r:
                return r
        for key in ("subtitles", "captions", "cues", "chunks"):
            lst = data.get(key)
            if isinstance(lst, list):
                r = _cues_from_subtitle_list(lst)
                if r:
                    return r
        res = data.get("result")
        if isinstance(res, dict) and isinstance(res.get("segments"), list):
            r = cues_from_segments_list(res["segments"])
            if r:
                return r
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if all("start" in x and "end" in x for x in data if isinstance(x, dict)):
            r = _cues_from_subtitle_list(data)
            if r:
                return r
    return None


def _cues_from_subtitle_list(items: list[Any]) -> list[tuple[float, float, str]] | None:
    cues: list[tuple[float, float, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        txt = _text_from_entry(item)
        if not txt:
            continue
        t0 = item.get("start")
        t1 = item.get("end")
        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
            ofs = item.get("offset")
            dur = item.get("duration")
            if isinstance(ofs, (int, float)) and isinstance(dur, (int, float)):
                o = float(ofs)
                d = float(dur)
                if o > 1_000_000:
                    o /= 1_000_000.0
                    d /= 1_000_000.0
                elif o > 10_000:
                    o /= 1000.0
                    d /= 1000.0
                cues.append((o, o + max(0.1, d), txt))
            continue
        else:
            a, b = float(t0), float(t1)
            if a > 1_000_000:
                a /= 1_000_000.0
                b /= 1_000_000.0
            elif a > 10_000 and b > 10_000:
                a /= 1000.0
                b /= 1000.0
            if b > a:
                cues.append((a, b, txt))
    if not cues:
        return None
    cues.sort(key=lambda x: x[0])
    return cues


def extract_plain_blocks(data: Any) -> list[str]:
    blocks: list[str] = []

    if isinstance(data, list):
        if all(isinstance(x, str) for x in data):
            return [x.strip() for x in data if isinstance(x, str) and x.strip()]
        for item in data:
            if isinstance(item, dict):
                t = _text_from_entry(item)
                if t:
                    blocks.append(t)
        return [b for b in blocks if b.strip()]

    if isinstance(data, dict):
        scenes = data.get("scenes")
        if isinstance(scenes, list):
            for s in scenes:
                if isinstance(s, dict):
                    t = str(s.get("narration") or "").strip()
                    if t:
                        blocks.append(t)
            if blocks:
                return blocks

        for key in ("lines", "paragraphs", "texts", "items", "script"):
            lst = data.get(key)
            if not isinstance(lst, list):
                continue
            for item in lst:
                if isinstance(item, str) and item.strip():
                    blocks.append(item.strip())
                elif isinstance(item, dict):
                    t = _text_from_entry(item)
                    if t:
                        blocks.append(t)
            if blocks:
                return [b for b in blocks if b.strip()]

        for key in ("narration", "subtitle", "body", "text"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return _split_text_plain(v)

    return [b for b in blocks if b.strip()]


def _evenly_time_blocks(
    blocks: list[str],
    *,
    seconds_per_block: float,
    total_duration: float | None,
) -> list[tuple[float, float, str]]:
    if not blocks:
        return []
    if total_duration is not None and total_duration > 0:
        dur = max(0.2, total_duration / len(blocks))
    else:
        dur = max(0.3, float(seconds_per_block))

    out: list[tuple[float, float, str]] = []
    t = 0.0
    for b in blocks:
        out.append((t, t + dur, b))
        t += dur
    return out


def document_to_srt(
    path: Path,
    *,
    seconds_per_block: float = 5.0,
    total_duration: float | None = None,
) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suf = path.suffix.lower()

    timed: list[tuple[float, float, str]] | None = None
    blocks: list[str] = []

    if suf == ".json" or raw.lstrip().startswith(("{", "[")):
        try:
            js: Any = json.loads(raw)
        except json.JSONDecodeError:
            js = None

        if js is not None:
            timed = extract_timed_cues(js)
            if timed is None and isinstance(js, dict):
                for subk in ("transcription", "data", "output", "payload"):
                    nest = js.get(subk)
                    if isinstance(nest, dict):
                        timed = extract_timed_cues(nest)
                        if timed:
                            break
                    if isinstance(nest, list):
                        timed = extract_timed_cues({"chunks": nest})
                        if timed:
                            break

            if timed:
                fixed: list[tuple[float, float, str]] = []
                for a, e, txt in sorted(timed, key=lambda x: x[0]):
                    if e <= a:
                        e = a + max(0.35, len(txt) * 0.08)
                    fixed.append((a, e, txt.strip()))
                return build_srt(fixed)

            blocks = extract_plain_blocks(js)

    if blocks:
        pass
    elif suf in (".md", ".markdown"):
        blocks = _split_markdown(raw)
        if not blocks:
            blocks = _split_text_plain(raw)
    else:
        blocks = _split_text_plain(raw)

    if not blocks:
        raise ValueError("자막으로 쓸 문장이 없습니다. scene.json(scenes[].narration), lines[], TXT/MD 단락 등을 지원합니다.")

    cues = _evenly_time_blocks(blocks, seconds_per_block=seconds_per_block, total_duration=total_duration)
    return build_srt(cues)
