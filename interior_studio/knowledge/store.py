"""ChromaDB wrapper для project knowledge."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from interior_studio.knowledge.chunking import KnowledgeChunk


class EmbeddingFunction(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _sanitize_collection_name(project_name: str) -> str:
    """Chroma требует ASCII [a-zA-Z0-9._-]; для кириллицы — стабильный hash."""
    ascii_part = re.sub(r"[^a-zA-Z0-9]", "", project_name)
    if len(ascii_part) >= 3:
        return f"proj_{ascii_part[:48]}"
    digest = hashlib.md5(project_name.encode("utf-8")).hexdigest()[:16]
    return f"proj_{digest}"


class KnowledgeStore:
    """Persistent ChromaDB store с embeddings (OpenAI или local)."""

    def __init__(
        self,
        persist_dir: str,
        embedding_fn: EmbeddingFunction | None = None,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        import chromadb

        if embedding_fn is None:
            from interior_studio.knowledge.embeddings import create_embedding_fn

            embedding_fn = create_embedding_fn()

        self._embedding_fn = embedding_fn
        self._client = chromadb.PersistentClient(path=persist_dir)

    def delete_collection(self, project_name: str) -> None:
        name = _sanitize_collection_name(project_name)
        try:
            self._client.delete_collection(name)
        except Exception:
            pass

    def _get_or_create_collection(self, project_name: str):
        name = _sanitize_collection_name(project_name)
        return self._client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def upsert_chunks(self, project_name: str, chunks: list[KnowledgeChunk]) -> int:
        if not chunks:
            return 0

        collection = self._get_or_create_collection(project_name)
        ids = [f"{c.source_path}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.to_metadata() for c in chunks]
        embeddings = self._embedding_fn.embed_documents(documents)

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(chunks)

    def search(
        self,
        project_name: str,
        query: str,
        *,
        top_k: int = 5,
        doc_type: str | None = None,
        room: str | None = None,
    ) -> list[dict]:
        collection = self._get_or_create_collection(project_name)
        query_embedding = self._embedding_fn.embed_query(query)

        where: dict | None = None
        filters: list[dict] = []
        if doc_type:
            filters.append({"doc_type": doc_type})
        if room:
            filters.append({"room": room})
        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        try:
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        if not result["ids"] or not result["ids"][0]:
            return []

        items: list[dict] = []
        for idx, doc_id in enumerate(result["ids"][0]):
            meta = result["metadatas"][0][idx] if result["metadatas"] else {}
            distance = result["distances"][0][idx] if result["distances"] else 1.0
            score = max(0.0, 1.0 - distance)
            items.append(
                {
                    "text": result["documents"][0][idx],
                    "source_path": meta.get("source_path", ""),
                    "doc_type": meta.get("doc_type"),
                    "stage": meta.get("stage") or None,
                    "room": meta.get("room") or None,
                    "score": round(score, 4),
                }
            )
        return items
