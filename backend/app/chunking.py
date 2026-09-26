from dataclasses import dataclass
import re

from .config import settings
from .extraction import ExtractedSection


TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class TextChunk:
    content: str
    chunk_index: int
    source_type: str
    source_label: str
    page_number: int | None
    slide_number: int | None
    token_count: int
    is_visual: bool = False


def estimate_token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text or ""))


def recursive_split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    target = chunk_size or settings.chunk_size
    overlap_tokens = overlap if overlap is not None else settings.chunk_overlap
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    words = cleaned.split()
    if len(words) <= target:
        return [cleaned]
    step = max(1, target - overlap_tokens)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        part = words[start : start + target]
        if not part:
            break
        chunks.append(" ".join(part))
        if start + target >= len(words):
            break
    return chunks


def chunk_sections(sections: list[ExtractedSection]) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for section in sections:
        parts = recursive_split_text(section.text)
        for part in parts:
            source_number = section.page_number if section.source_type == "pdf" else section.slide_number
            source_name = "Halaman" if section.source_type == "pdf" else "Slide"
            suffix = " (visual)" if section.is_visual else ""
            chunks.append(
                TextChunk(
                    content=part,
                    chunk_index=len(chunks),
                    source_type=section.source_type,
                    source_label=f"{source_name} {source_number}{suffix}",
                    page_number=section.page_number,
                    slide_number=section.slide_number,
                    token_count=estimate_token_count(part),
                    is_visual=section.is_visual,
                )
            )
    return chunks
