"""Сервис web search — JSON для tool."""

from __future__ import annotations

import json

from interior_studio.config import (
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_PROVIDER,
    WEB_SEARCH_REGION,
)
from interior_studio.web.client import DuckDuckGoClient, WebSearchClient


def _default_client() -> WebSearchClient:
    if WEB_SEARCH_PROVIDER == "duckduckgo":
        return DuckDuckGoClient()
    raise ValueError(f"Unsupported WEB_SEARCH_PROVIDER: {WEB_SEARCH_PROVIDER}")


def search_web(
    query: str,
    max_results: int | None = None,
    *,
    client: WebSearchClient | None = None,
) -> str:
    """Ищет в интернете; возвращает JSON-строку для tool."""
    query = query.strip()
    if not query:
        return json.dumps(
            {"ok": False, "message": "Query cannot be empty"},
            ensure_ascii=False,
        )

    limit = WEB_SEARCH_MAX_RESULTS
    if max_results is not None:
        limit = min(max_results, WEB_SEARCH_MAX_RESULTS)

    search_client = client or _default_client()
    try:
        results = search_client.search(
            query,
            max_results=limit,
            region=WEB_SEARCH_REGION,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "message": f"Web search failed: {exc}"},
            ensure_ascii=False,
        )

    return json.dumps(
        {"ok": True, "query": query, "results": results},
        ensure_ascii=False,
    )
