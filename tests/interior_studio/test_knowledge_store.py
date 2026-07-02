"""Тесты Chroma store (mock embeddings)."""

from __future__ import annotations

from interior_studio.knowledge.chunking import KnowledgeChunk
from interior_studio.knowledge.store import KnowledgeStore
from tests.interior_studio.knowledge_fixtures import MockEmbeddings


def test_store_upsert_and_search_roundtrip(tmp_path):
    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma"),
        embedding_fn=MockEmbeddings(),
    )
    chunks = [
        KnowledgeChunk(
            text="Цвет дверей тёплый белый, ручки Лирика.",
            project_name="ЖК Шкиперский",
            source_path="Исходные материалы/Общее бриф.pdf",
            stage="Исходные материалы",
            room=None,
            doc_type="brief",
            chunk_index=0,
        ),
        KnowledgeChunk(
            text="Плитка Equipe Artisan в мастер-санузле.",
            project_name="ЖК Шкиперский",
            source_path="Выезды авторский/Отчеты по выездам.docx",
            stage="Выезды авторский",
            room=None,
            doc_type="site_report",
            chunk_index=0,
        ),
    ]
    count = store.upsert_chunks("ЖК Шкиперский", chunks)
    assert count == 2

    results = store.search("ЖК Шкиперский", "цвет дверей", top_k=5)
    assert results
    assert any("двер" in r["text"].lower() for r in results)

    filtered = store.search(
        "ЖК Шкиперский",
        "плитка",
        top_k=5,
        doc_type="site_report",
    )
    assert filtered
    assert all(r["doc_type"] == "site_report" for r in filtered)


def test_store_delete_collection(tmp_path):
    store = KnowledgeStore(
        persist_dir=str(tmp_path / "chroma2"),
        embedding_fn=MockEmbeddings(),
    )
    chunk = KnowledgeChunk(
        text="Тестовый фрагмент для удаления коллекции.",
        project_name="Test",
        source_path="a/b.pdf",
        stage=None,
        room=None,
        doc_type="brief",
        chunk_index=0,
    )
    store.upsert_chunks("Test", [chunk])
    store.delete_collection("Test")
    results = store.search("Test", "тест", top_k=3)
    assert results == []
