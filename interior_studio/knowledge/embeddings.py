"""Фабрика embedding-функций для project knowledge (OpenAI или локально)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interior_studio.knowledge.store import EmbeddingFunction


def create_embedding_fn(provider: str | None = None) -> EmbeddingFunction:
    """Создаёт embedder по EMBEDDING_PROVIDER из config (openai | local)."""
    from interior_studio.config import (
        EMBEDDING_PROVIDER,
        LOCAL_EMBEDDING_MODEL,
        OPENAI_API_KEY,
        OPENAI_EMBEDDING_MODEL,
    )

    selected = (provider or EMBEDDING_PROVIDER).strip().lower()

    if selected == "openai":
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai. "
                "Set the key in .env or use EMBEDDING_PROVIDER=local."
            )
        from langchain_openai import OpenAIEmbeddings

        lc_embeddings = OpenAIEmbeddings(
            model=OPENAI_EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
        )

        class _OpenAIAdapter:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return lc_embeddings.embed_documents(texts)

            def embed_query(self, text: str) -> list[float]:
                return lc_embeddings.embed_query(text)

        return _OpenAIAdapter()

    if selected == "local":
        return LocalEmbeddings(model=LOCAL_EMBEDDING_MODEL)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER: {selected!r}. Supported: 'openai', 'local'."
    )


class LocalEmbeddings:
    """Локальные embeddings через sentence-transformers (без OpenAI API)."""

    def __init__(self, model: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()
