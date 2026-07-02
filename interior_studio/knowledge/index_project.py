"""CLI: обход папки проекта → extract → chunk → Chroma."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from interior_studio.config import CHROMA_PERSIST_DIR, OPENAI_EMBEDDING_MODEL
from interior_studio.db.connection import create_db_engine, init_schema, session_scope
from interior_studio.db.models import Project, ProjectKnowledgeSource
from interior_studio.knowledge.chunking import build_chunks
from interior_studio.knowledge.extractors import (
    classify_doc_type,
    extract_text,
    should_skip_path,
)
from interior_studio.knowledge.store import KnowledgeStore


def collect_tier1_files(root: Path) -> list[tuple[Path, str]]:
    """Возвращает (absolute_path, relative_path) для Tier 1 файлов."""
    files: list[tuple[Path, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if should_skip_path(rel):
            continue
        if classify_doc_type(rel) is None:
            continue
        files.append((path, rel))
    return sorted(files, key=lambda x: x[1])


def index_project_folder(
    session,
    *,
    project_name: str,
    root_path: Path,
    reset: bool = False,
    store: KnowledgeStore | None = None,
) -> dict:
    project = session.scalar(select(Project).where(Project.name == project_name))
    if not project:
        raise ValueError(f"Project '{project_name}' not found in database. Seed it first.")

    knowledge_store = store or KnowledgeStore(
        persist_dir=CHROMA_PERSIST_DIR,
        embedding_model=OPENAI_EMBEDDING_MODEL,
    )

    if reset:
        knowledge_store.delete_collection(project_name)

    all_chunks = []
    indexed_files = 0
    for file_path, rel_path in collect_tier1_files(root_path):
        doc_type = classify_doc_type(rel_path)
        if doc_type is None:
            continue
        try:
            text = extract_text(file_path)
        except Exception:
            continue
        chunks = build_chunks(
            text,
            project_name=project_name,
            source_path=rel_path,
            doc_type=doc_type,
        )
        if chunks:
            indexed_files += 1
            all_chunks.extend(chunks)

    chunk_count = knowledge_store.upsert_chunks(project_name, all_chunks)

    source = session.get(ProjectKnowledgeSource, project.id)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if source is None:
        source = ProjectKnowledgeSource(
            project_id=project.id,
            local_path=str(root_path),
            indexed_at=now,
            chunk_count=chunk_count,
        )
        session.add(source)
    else:
        source.local_path = str(root_path)
        source.indexed_at = now
        source.chunk_count = chunk_count

    session.flush()

    return {
        "project_name": project_name,
        "files_indexed": indexed_files,
        "chunk_count": chunk_count,
        "local_path": str(root_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Index project knowledge documents into ChromaDB")
    parser.add_argument("--project", required=True, help="Project name in database")
    parser.add_argument("--path", required=True, help="Root folder with project documents")
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild Chroma collection")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.is_dir():
        raise SystemExit(f"Path not found or not a directory: {root}")

    engine = create_db_engine()
    init_schema(engine)

    with session_scope(engine=engine) as session:
        result = index_project_folder(
            session,
            project_name=args.project,
            root_path=root.resolve(),
            reset=args.reset,
        )

    print(
        f"Indexed project '{result['project_name']}': "
        f"files={result['files_indexed']}, chunks={result['chunk_count']}, "
        f"path={result['local_path']}"
    )


if __name__ == "__main__":
    main()
