"""긴 본문을 백엔드 한도에 맞게 나눕니다."""

from __future__ import annotations


def split_for_tts(text: str, max_chars: int) -> list[str]:
    """빈 줄(문단) 우선으로 자르고, 여전히 길면 max_chars 단위로 자릅니다."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append("\n\n".join(buf))
            buf = []
            buf_len = 0

    for para in paragraphs:
        plen = len(para) + (2 if buf else 0)
        if plen > max_chars:
            flush()
            chunks.extend(_split_oversized_paragraph(para, max_chars))
            continue
        if buf_len + plen > max_chars:
            flush()
        buf.append(para)
        buf_len += plen
    flush()
    return chunks


def _split_oversized_paragraph(para: str, max_chars: int) -> list[str]:
    out: list[str] = []
    start = 0
    n = len(para)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            cut = para.rfind(" ", start, end)
            if cut > start + max_chars // 2:
                end = cut + 1
        piece = para[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    return out or [para[:max_chars]]
