"""Тесты tool search_project_knowledge."""

from __future__ import annotations

import json

from interior_studio.agent.tools.knowledge import search_project_knowledge_impl
from interior_studio.knowledge.chunking import KnowledgeChunk
from interior_studio.knowledge.store import KnowledgeStore
from interior_studio.services import project_service, user_context
from tests.interior_studio.knowledge_fixtures import MockEmbeddings


def test_tool_search_project_knowledge(db_session, tmp_path, monkeypatch):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    store.upsert_chunks(
        "ЖК Шкиперский",
        [
            KnowledgeChunk(
                text="Кухня с островом и барными стульями согласована в брифе.",
                project_name="ЖК Шкиперский",
                source_path="Исходные материалы/Общее бриф.pdf",
                stage="Исходные материалы",
                room=None,
                doc_type="brief",
                chunk_index=0,
            ),
        ],
    )

    monkeypatch.setattr(
        "interior_studio.knowledge.search.KnowledgeStore",
        lambda *args, **kwargs: store,
    )

    raw = search_project_knowledge_impl(db_session, 111111111, "кухня остров")
    data = json.loads(raw)
    assert data["ok"] is True
    assert data["results"]
