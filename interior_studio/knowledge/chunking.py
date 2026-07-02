"""Разбиение текста на чанки с metadata."""

from __future__ import annotations

from dataclasses import dataclass

from interior_studio.knowledge.extractors import MIN_TEXT_CHARS, parse_stage_and_room


@dataclass
class KnowledgeChunk:
    text: str
    project_name: str
    source_path: str
    stage: str | None
    room: str | None
    doc_type: str
    chunk_index: int

    def to_metadata(self) -> dict:
        return {
            "project_name": self.project_name,
            "source_path": self.source_path,
            "stage": self.stage or "",
            "room": self.room or "",
            "doc_type": self.doc_type,
            "chunk_index": self.chunk_index,
        }


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Разбивает текст по абзацам, целевой размер ~500–800 символов."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) + 1 > max_chars and current:
            chunks.append("\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 1

    if current:
        chunks.append("\n".join(current))
    return chunks


def build_chunks(
    text: str,
    *,
    project_name: str,
    source_path: str,
    doc_type: str,
    max_chars: int = 800,
) -> list[KnowledgeChunk]:
    """Создаёт чанки с metadata; пустой список если текст слишком короткий."""
    if len(text.strip()) < MIN_TEXT_CHARS:
        return []

    stage, room = parse_stage_and_room(source_path)
    raw_chunks = chunk_text(text, max_chars=max_chars)
    return [
        KnowledgeChunk(
            text=chunk,
            project_name=project_name,
            source_path=source_path,
            stage=stage,
            room=room,
            doc_type=doc_type,
            chunk_index=idx,
        )
        for idx, chunk in enumerate(raw_chunks)
    ]
