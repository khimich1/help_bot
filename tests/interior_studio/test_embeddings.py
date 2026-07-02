"""Тесты фабрики embeddings."""

from __future__ import annotations

import pytest

from interior_studio.knowledge.embeddings import create_embedding_fn


def test_create_embedding_fn_unknown_provider():
    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        create_embedding_fn("yandex")


def test_create_embedding_fn_openai_requires_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from interior_studio import config

    config.OPENAI_API_KEY = None

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        create_embedding_fn("openai")
