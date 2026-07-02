"""Абстракция провайдера web search (DuckDuckGo MVP)."""

from __future__ import annotations

from typing import Protocol

from duckduckgo_search import DDGS


class WebSearchClient(Protocol):
    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "ru-ru",
    ) -> list[dict[str, str]]:
        """Returns [{"title", "url", "snippet"}, ...]"""


class DuckDuckGoClient:
    """Поиск через duckduckgo-search (DDGS.text)."""

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        region: str = "ru-ru",
    ) -> list[dict[str, str]]:
        with DDGS() as ddgs:
            raw = list(
                ddgs.text(
                    keywords=query,
                    max_results=max_results,
                    region=region,
                )
            )
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            }
            for item in raw
        ]
