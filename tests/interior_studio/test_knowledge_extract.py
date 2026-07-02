"""Тесты extractors для project knowledge."""

from __future__ import annotations

from pathlib import Path

import pytest

from interior_studio.knowledge.extractors import (
    classify_doc_type,
    extract_docx,
    extract_pdf,
    should_skip_path,
)
from tests.interior_studio.knowledge_fixtures import (
    _write_minimal_docx,
    _write_minimal_pdf,
    knowledge_fixtures_dir,
)


def test_classify_doc_type_patterns():
    assert classify_doc_type("Исходные материалы/Общее бриф.pdf") == "brief"
    assert classify_doc_type("Исходные материалы/Анкета клиента.pdf") == "questionnaire"
    assert classify_doc_type("Выезды авторский/Отчеты по выездам.docx") == "site_report"
    assert classify_doc_type("Рендеры/кухня.jpg") is None


def test_should_skip_stale_paths():
    assert should_skip_path("Неактуальное/бриф.pdf") is True
    assert should_skip_path("архив/старая/док.pdf") is True
    assert should_skip_path("Исходные материалы/Общее.pdf") is False


def test_extract_pdf_and_docx(tmp_path: Path):
    pdf_path = tmp_path / "test.pdf"
    docx_path = tmp_path / "test.docx"
    _write_minimal_pdf(pdf_path, "Текст PDF про двери белого цвета для теста извлечения.")
    _write_minimal_docx(docx_path, "Текст DOCX про плитку в санузле для теста извлечения.")

    pdf_text = extract_pdf(pdf_path)
    docx_text = extract_docx(docx_path)

    assert "двери" in pdf_text.lower() or "PDF" in pdf_text
    assert len(docx_text) >= 50


def test_knowledge_fixtures_tree(knowledge_fixtures_dir: Path):
    assert (knowledge_fixtures_dir / "Исходные материалы" / "Общее бриф.pdf").exists()
    assert should_skip_path("Неактуальное/старый бриф.pdf") is True
