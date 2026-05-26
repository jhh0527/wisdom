from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoItem:
    video_id: str
    title: str
    channel: str
    view_count: int
    like_count: int | None
    comment_count: int | None
    published_at: str
    duration: str
    category_id: str | None = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"
