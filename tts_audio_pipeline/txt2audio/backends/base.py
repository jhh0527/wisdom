"""백엔드 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SynthesisBackend(ABC):
    @abstractmethod
    async def synthesize_file(self, text: str, output_path: Path) -> None:
        """전체 텍스트를 한 개의 오디오 파일로 저장합니다."""
