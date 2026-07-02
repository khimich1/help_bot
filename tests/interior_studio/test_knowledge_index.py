"""Тесты CLI index_project."""

from __future__ import annotations

from interior_studio.knowledge.index_project import index_project_folder
from interior_studio.knowledge.store import KnowledgeStore
from interior_studio.services import project_service
from tests.interior_studio.knowledge_fixtures import MockEmbeddings, knowledge_fixtures_dir


def test_index_project_folder(db_session, knowledge_fixtures_dir, tmp_path):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    db_session.commit()

    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    result = index_project_folder(
        db_session,
        project_name="ЖК Шкиперский",
        root_path=knowledge_fixtures_dir,
        store=store,
    )

    assert result["chunk_count"] > 0
    assert result["files_indexed"] >= 2

    from interior_studio.db.models import ProjectKnowledgeSource

    source = db_session.get(ProjectKnowledgeSource, project.id)
    assert source is not None
    assert source.chunk_count == result["chunk_count"]
    assert source.local_path
