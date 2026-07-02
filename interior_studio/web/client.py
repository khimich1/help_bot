"""Абстракция провайдера web search (DuckDuckGo MVP)."""

from __future__ import annotations

from typing import Protocol

from ddgs import DDGS
from ddgs.exceptions import DDGSException

# Порядок: сначала duckduckgo, при пустоте / No results found — auto (metasearch).
_SEARCH_BACKENDS = ("duckduckgo", "auto")


class WebSearchClient(Protocol):
    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "ru-ru",
    ) -> list[dict[str, str]]:
        """Returns [{"title", "url", "snippet"}, ...]"""


def _normalize_results(raw: list[dict] | None) -> list[dict[str, str]]:
    items = raw if raw else []
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
        }
        for item in items
    ]


class DuckDuckGoClient:
    """Поиск через ddgs с fallback между backend'ами."""

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "ru-ru",
    ) -> list[dict[str, str]]:
        last_no_results = False
        for backend in _SEARCH_BACKENDS:
            try:
                raw = DDGS().text(
                    query,
                    max_results=max_results,
                    region=region,
                    backend=backend,
                )
            except DDGSException as exc:
                if "No results found" in str(exc):
                    last_no_results = True
                    continue
                raise

            results = _normalize_results(raw)
            if results:
                return results
            last_no_results = True

        if last_no_results:
            return []
        return []
