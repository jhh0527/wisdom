# -*- coding: utf-8 -*-
"""로스차일드.txt → scene.json 형식 JSON (한 번 실행용 또는 재사용)."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _is_section_heading(s: str) -> bool:
    """짧은 절 제목(마침표·물음표 없음)만 장면 제목으로 인식."""
    s = s.strip()
    if not s or "\n" in s:
        return False
    if len(s) > 56 or len(s) < 3:
        return False
    last = s[-1]
    if last in ".。!?？!…":
        return False
    if "입니다" in s or "습니다" in s or "하세요" in s or "보겠습니다" in s:
        return False
    return True


def txt_to_scene_doc(text: str, *, doc_title: str = "로스차일드 가문") -> dict:
    text = text.replace("\r\n", "\n").strip()
    chunks = [c.strip() for c in re.split(r"\n\s*\n+", text) if c.strip()]

    scenes: list[dict] = []
    cur_title = "오프닝"
    cur_chunks: list[str] = []

    def flush() -> None:
        nonlocal cur_chunks, cur_title, scenes
        if not cur_chunks:
            return
        narr = re.sub(r"\s+", " ", "\n".join(cur_chunks)).strip()
        if not narr:
            cur_chunks = []
            return
        i = len(scenes) + 1
        scenes.append(
            {
                "id": f"scene{i}",
                "title": cur_title,
                "narration": narr,
                "image_prompt": "19세기 유럽 금융·역사 다큐멘터리 톤, 유화·판화풍 일러스트, 차분한 조명",
                "image_file": f"images/scene{i}.png",
                "audio_file": f"audio/scene{i}.mp3",
                "subtitle_file": f"subtitles/scene{i}.srt",
            }
        )
        cur_chunks = []

    for ch in chunks:
        lines = [ln.strip() for ln in ch.split("\n") if ln.strip()]
        if len(lines) == 1 and _is_section_heading(lines[0]):
            flush()
            cur_title = lines[0]
            continue
        cur_chunks.append(ch)

    flush()

    # 너무 짧은 장면은 앞 장면 내레이션에 이어 붙임(문장이 단락 경계에서 잘린 경우)
    merged: list[dict] = []
    for sc in scenes:
        narr = sc["narration"].strip()
        if merged and len(narr) < 90:
            prev = merged[-1]
            prev["narration"] = (prev["narration"].rstrip() + " " + narr).strip()
            continue
        merged.append(sc)

    for i, sc in enumerate(merged, start=1):
        sc["id"] = f"scene{i}"
        sc["image_file"] = f"images/scene{i}.png"
        sc["audio_file"] = f"audio/scene{i}.mp3"
        sc["subtitle_file"] = f"subtitles/scene{i}.srt"

    return {
        "title": doc_title,
        "scenes": merged,
        "settings": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "video_codec": "libx264",
            "audio_codec": "aac",
            "youtube_faststart": True,
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    src = root / "로스차일드.txt"
    if not src.is_file():
        raise SystemExit(f"없음: {src}")
    doc = txt_to_scene_doc(src.read_text(encoding="utf-8"))
    out = root / "로스차일드.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"작성: {out} (장면 {len(doc['scenes'])}개)")


if __name__ == "__main__":
    main()
