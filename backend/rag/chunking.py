from __future__ import annotations

from typing import Iterable


def estimate_tokens(text: str) -> int:
    return max(1, int(round(len(text) / 4))) if text else 0


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if stripped.endswith(":"):
        return True
    words = stripped.split()
    if 1 <= len(words) <= 12 and sum(word[:1].isupper() for word in words) >= max(1, len(words) // 2):
        return True
    return False


def heading_aware_chunks(
    text: str,
    *,
    max_chars: int = 900,
    overlap_chars: int = 120,
) -> Iterable[dict[str, object]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    chunks: list[dict[str, object]] = []
    section_path: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        payload = " ".join(buffer).strip()
        if not payload:
            return
        start = 0
        while start < len(payload):
            end = min(len(payload), start + max_chars)
            chunk_text = payload[start:end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "text": chunk_text,
                        "section_path": list(section_path),
                        "token_count": estimate_tokens(chunk_text),
                    }
                )
            if end >= len(payload):
                break
            start = max(start + 1, end - overlap_chars)

    for line in lines:
        if _looks_like_heading(line):
            flush()
            buffer = []
            if len(section_path) >= 3:
                section_path = section_path[-2:]
            section_path.append(line)
            continue
        buffer.append(" ".join(line.split()))

    flush()
    return chunks
