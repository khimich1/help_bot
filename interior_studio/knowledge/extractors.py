"""Извлечение текста из PDF и DOCX для индексации."""

from __future__ import annotations

from pathlib import Path

SKIP_PATH_PARTS = ("Неактуальное", "старая")
TIER1_EXTENSIONS = {".pdf", ".docx"}
MIN_TEXT_CHARS = 50


def should_skip_path(relative_path: str) -> bool:
    """Пропускает устаревшие папки и неподдерживаемые расширения."""
    normalized = relative_path.replace("\\", "/")
    for part in SKIP_PATH_PARTS:
        if part in normalized:
            return True
    ext = Path(normalized).suffix.lower()
    return ext not in TIER1_EXTENSIONS


def classify_doc_type(relative_path: str) -> str | None:
    """Определяет doc_type по паттернам Tier 1 из спеки."""
    rel = relative_path.replace("\\", "/")
    lower = rel.lower()
    name = Path(lower).name

    if "исходные материалы" in lower and name.startswith("общее") and name.endswith(".pdf"):
        return "brief"
    if "исходные материалы" in lower and name.startswith("анкета") and name.endswith(".pdf"):
        return "questionnaire"
    if name == "отчеты по выездам.docx":
        return "site_report"
    return None


def parse_stage_and_room(relative_path: str) -> tuple[str | None, str | None]:
    """Первый уровень папки — stage; второй — room (если есть)."""
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
    if len(parts) < 2:
        return None, None
    stage = parts[0]
    room = parts[1] if len(parts) >= 3 else None
    return stage, room


def extract_pdf(file_path: Path) -> str:
    import fitz

    doc = fitz.open(file_path)
    try:
        parts = [page.get_text() for page in doc]
        return "\n".join(parts).strip()
    finally:
        doc.close()


def extract_docx(file_path: Path) -> str:
    from docx import Document

    document = Document(file_path)
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(parts).strip()


def extract_text(file_path: Path) -> str:
    """Извлекает текст из PDF или DOCX."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(file_path)
    if ext == ".docx":
        return extract_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}")
