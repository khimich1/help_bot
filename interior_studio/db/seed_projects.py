"""Seed проектов из текстового файла (по одному названию на строку)."""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from interior_studio.db.connection import create_db_engine, init_schema, session_scope
from interior_studio.db.models import Project


def seed_projects_from_file(session: Session, file_path: str) -> dict[str, int]:
    """Добавляет проекты из файла. Повторный запуск не падает (idempotent)."""
    created = 0
    skipped = 0
    with open(file_path, encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    for name in names:
        existing = session.scalar(select(Project).where(Project.name == name))
        if existing:
            skipped += 1
            continue
        session.add(Project(name=name, status="active"))
        created += 1

    return {"created": created, "skipped": skipped, "total_in_file": len(names)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed projects from a text file")
    parser.add_argument("--file", required=True, help="Path to file with project names")
    args = parser.parse_args()

    engine = create_db_engine()
    init_schema(engine)

    with session_scope(engine=engine) as session:
        result = seed_projects_from_file(session, args.file)

    print(
        f"Seed complete: created={result['created']}, "
        f"skipped={result['skipped']}, total={result['total_in_file']}"
    )


if __name__ == "__main__":
    main()
