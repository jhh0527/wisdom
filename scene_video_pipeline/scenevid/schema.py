"""scene.json 로드·저장 및 기본 검증."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RenderSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    youtube_faststart: bool = True


@dataclass
class Scene:
    id: str
    title: str
    narration: str
    image_prompt: str = ""
    # 상대경로(project root 기준 권장)
    image_file: str = ""
    audio_file: str = ""
    subtitle_file: str = ""

    def resolved_paths(self, root: Path) -> tuple[Path, Path, Path]:
        img = root / (self.image_file or f"images/{self.id}.png")
        aud = root / (self.audio_file or f"audio/{self.id}.mp3")
        sub = root / (self.subtitle_file or f"subtitles/{self.id}.srt")
        return img, aud, sub


@dataclass
class ProjectDoc:
    title: str
    scenes: list[Scene]
    settings: RenderSettings = field(default_factory=RenderSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "scenes": [
                {
                    "id": s.id,
                    "title": s.title,
                    "narration": s.narration,
                    "image_prompt": s.image_prompt,
                    "image_file": s.image_file or f"images/{s.id}.png",
                    "audio_file": s.audio_file or f"audio/{s.id}.mp3",
                    "subtitle_file": s.subtitle_file or f"subtitles/{s.id}.srt",
                }
                for s in self.scenes
            ],
            "settings": asdict(self.settings),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ProjectDoc:
        scenes_raw = data.get("scenes") or []
        scenes: list[Scene] = []
        for item in scenes_raw:
            scenes.append(
                Scene(
                    id=str(item["id"]),
                    title=str(item.get("title") or item["id"]),
                    narration=str(item.get("narration") or "").strip(),
                    image_prompt=str(item.get("image_prompt") or ""),
                    image_file=str(item.get("image_file") or ""),
                    audio_file=str(item.get("audio_file") or ""),
                    subtitle_file=str(item.get("subtitle_file") or ""),
                )
            )
        st = data.get("settings") or {}
        settings = RenderSettings(
            width=int(st.get("width", 1920)),
            height=int(st.get("height", 1080)),
            fps=int(st.get("fps", 30)),
            video_codec=str(st.get("video_codec", "libx264")),
            audio_codec=str(st.get("audio_codec", "aac")),
            youtube_faststart=bool(st.get("youtube_faststart", True)),
        )
        return ProjectDoc(
            title=str(data.get("title") or "Untitled"),
            scenes=scenes,
            settings=settings,
        )


def load_project(path: Path) -> ProjectDoc:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectDoc.from_dict(data)


def save_project(doc: ProjectDoc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
