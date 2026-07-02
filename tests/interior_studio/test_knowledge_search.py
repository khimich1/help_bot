"""Тесты search service."""

from __future__ import annotations

import json

from interior_studio.knowledge.chunking import KnowledgeChunk
from interior_studio.knowledge.search import search_project_knowledge
from interior_studio.knowledge.store import KnowledgeStore
from interior_studio.services import project_service, user_context
from tests.interior_studio.knowledge_fixtures import MockEmbeddings


def _seed_indexed_project(db_session, tmp_path):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    store.upsert_chunks(
        "ЖК Шкиперский",
        [
            KnowledgeChunk(
                text="Цвет дверей тёплый белый, фурнитура Лирика.",
                project_name="ЖК Шкиперский",
                source_path="Исходные материалы/Общее бриф.pdf",
                stage="Исходные материалы",
                room=None,
                doc_type="brief",
                chunk_index=0,
            ),
        ],
    )
    return project, store


def test_search_returns_results(db_session, tmp_path):
    _seed_indexed_project(db_session, tmp_path)
    db_session.commit()

    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    raw = search_project_knowledge(
        db_session,
        111111111,
        "цвет дверей",
        store=store,
    )
    data = json.loads(raw)
    assert data["ok"] is True
    assert data["project_name"] == "ЖК Шкиперский"
    assert len(data["results"]) >= 1


def test_search_empty_without_active_project(db_session, tmp_path):
    project_service.create_project(db_session, "ЖК Шкиперский")
    db_session.commit()

    raw = search_project_knowledge(db_session, 111111111, "двери")
    data = json.loads(raw)
    assert data["ok"] is False


def test_search_doc_type_filter(db_session, tmp_path):
    _seed_indexed_project(db_session, tmp_path)
    db_session.commit()

    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    store.upsert_chunks(
        "ЖК Шкиперский",
        [
            KnowledgeChunk(
                text="Плитка Equipe Artisan sage в мастер-санузле.",
                project_name="ЖК Шкиперский",
                source_path="Выезды/Отчеты по выездам.docx",
                stage="Выезды",
                room=None,
                doc_type="site_report",
                chunk_index=0,
            ),
        ],
    )
    raw = search_project_knowledge(
        db_session,
        111111111,
        "плитка",
        doc_type="site_report",
        store=store,
    )
    data = json.loads(raw)
    assert data["ok"] is True
    assert all(r["doc_type"] == "site_report" for r in data["results"])
