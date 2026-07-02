"""Тесты chunking для project knowledge."""

from __future__ import annotations

from interior_studio.knowledge.chunking import build_chunks, chunk_text


def test_chunk_text_splits_long_text():
    text = "\n".join(f"Абзац номер {i} с достаточным количеством символов для чанка." for i in range(20))
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(c) <= 250 for c in chunks)


def test_build_chunks_metadata():
    text = "Цвет дверей тёплый белый. Ручки модели Лирика. " * 5
    chunks = build_chunks(
        text,
        project_name="ЖК Шкиперский",
        source_path="Выезды авторский/Фото/Отчеты по выездам.docx",
        doc_type="site_report",
    )
    assert chunks
    assert chunks[0].project_name == "ЖК Шкиперский"
    assert chunks[0].stage == "Выезды авторский"
    assert chunks[0].doc_type == "site_report"
    assert chunks[0].chunk_index == 0


def test_build_chunks_skips_short_text():
    assert build_chunks(
        "коротко",
        project_name="ЖК Шкиперский",
        source_path="a/b.pdf",
        doc_type="brief",
    ) == []
