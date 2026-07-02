"""Фикстуры для knowledge-тестов."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


class MockEmbeddings:
    """Детерминированные эмбеддинги без OpenAI API."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:32]]


@pytest.fixture
def mock_embeddings() -> MockEmbeddings:
    return MockEmbeddings()


@pytest.fixture
def knowledge_fixtures_dir(tmp_path: Path) -> Path:
    """Минимальное дерево Tier 1 документов для индексации."""
    root = tmp_path / "project_docs"
    brief_dir = root / "Исходные материалы"
    brief_dir.mkdir(parents=True)
    brief_pdf = brief_dir / "Общее бриф.pdf"
    _write_minimal_pdf(
        brief_pdf,
        "Стиль интерьера: современная классика. Цвет дверей: тёплый белый, ручки Лирика.",
    )

    report_dir = root / "Выезды авторский" / "Фото с выездов"
    report_dir.mkdir(parents=True)
    report_docx = report_dir / "Отчеты по выездам.docx"
    _write_minimal_docx(
        report_docx,
        "Мастер-санузел: плитка Equipe Artisan 7.5x30, цвет sage. "
        "Клиент согласовал замену обоев в коридоре на фактурные.",
    )

    stale_dir = root / "Неактуальное"
    stale_dir.mkdir()
    _write_minimal_pdf(stale_dir / "старый бриф.pdf", "Устаревшие данные не должны индексироваться.")

    return root


def _write_minimal_pdf(path: Path, text: str) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()


def _write_minimal_docx(path: Path, text: str) -> None:
    from docx import Document

    document = Document()
    for paragraph in text.split(". "):
        if paragraph.strip():
            document.add_paragraph(paragraph.strip())
    document.save(path)
