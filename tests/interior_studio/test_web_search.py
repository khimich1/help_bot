"""Unit-тесты web search service (mock client, без интернета)."""

from __future__ import annotations

import json

from interior_studio.web.search import search_web


class MockWebClient:
    def __init__(self, results: list[dict[str, str]] | None = None, error: Exception | None = None):
        self.results = results or []
        self.error = error
        self.last_call: dict | None = None

    def search(self, query: str, *, max_results: int = 5, region: str = "ru-ru") -> list[dict[str, str]]:
        self.last_call = {
            "query": query,
            "max_results": max_results,
            "region": region,
        }
        if self.error:
            raise self.error
        return self.results


def test_search_web_success():
    client = MockWebClient(
        results=[
            {
                "title": "Провайдеры интернета",
                "url": "https://example.com/isp",
                "snippet": "Ростелеком и МТС в ЖК.",
            }
        ]
    )
    raw = search_web("интернет ЖК Шкиперский", client=client)
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["query"] == "интернет ЖК Шкиперский"
    assert len(data["results"]) == 1
    assert data["results"][0]["url"] == "https://example.com/isp"
    assert client.last_call == {
        "query": "интернет ЖК Шкиперский",
        "max_results": 5,
        "region": "ru-ru",
    }


def test_search_web_empty_results():
    client = MockWebClient(results=[])
    raw = search_web("нет результатов", client=client)
    data = json.loads(raw)

    assert data == {"ok": True, "query": "нет результатов", "results": []}


def test_search_web_no_results_not_treated_as_hard_error():
    """Пустой ответ клиента — ok:true results:[], не ok:false."""
    client = MockWebClient(results=[])
    raw = search_web("провайдер интернета ЖК", client=client)
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["results"] == []
    assert "Web search failed" not in json.dumps(data)


def test_search_web_provider_error():
    client = MockWebClient(error=RuntimeError("DDG blocked"))
    raw = search_web("тест", client=client)
    data = json.loads(raw)

    assert data["ok"] is False
    assert "Web search failed" in data["message"]
    assert "DDG blocked" in data["message"]


def test_search_web_empty_query():
    client = MockWebClient()
    raw = search_web("   ", client=client)
    data = json.loads(raw)

    assert data == {"ok": False, "message": "Query cannot be empty"}
    assert client.last_call is None


def test_search_web_max_results_capped(monkeypatch):
    monkeypatch.setattr("interior_studio.web.search.WEB_SEARCH_MAX_RESULTS", 5)
    client = MockWebClient(results=[])
    search_web("тест", max_results=10, client=client)
    assert client.last_call["max_results"] == 5


def test_search_web_custom_max_results(monkeypatch):
    monkeypatch.setattr("interior_studio.web.search.WEB_SEARCH_MAX_RESULTS", 5)
    client = MockWebClient(results=[])
    search_web("тест", max_results=3, client=client)
    assert client.last_call["max_results"] == 3


def test_search_web_region_from_config(monkeypatch):
    monkeypatch.setattr("interior_studio.web.search.WEB_SEARCH_REGION", "wt-wt")
    client = MockWebClient(results=[])
    search_web("тест", client=client)
    assert client.last_call["region"] == "wt-wt"
