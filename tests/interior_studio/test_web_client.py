"""Unit-тесты DuckDuckGoClient (mock ddgs, без интернета)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from ddgs.exceptions import DDGSException

from interior_studio.web.client import DuckDuckGoClient


def test_client_returns_results_from_first_backend(monkeypatch):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "ISP", "href": "https://example.com", "body": "snippet"}
    ]
    monkeypatch.setattr("interior_studio.web.client.DDGS", lambda: mock_ddgs)

    results = DuckDuckGoClient().search("интернет ЖК", max_results=3, region="ru-ru")

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
    mock_ddgs.text.assert_called_once_with(
        "интернет ЖК",
        max_results=3,
        region="ru-ru",
        backend="duckduckgo",
    )


def test_client_falls_back_to_auto_on_no_results(monkeypatch):
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = [
        DDGSException("No results found."),
        [{"title": "Адрес", "href": "https://cian.ru/x", "body": "Галерный"}],
    ]
    monkeypatch.setattr("interior_studio.web.client.DDGS", lambda: mock_ddgs)

    results = DuckDuckGoClient().search("ЖК Шкиперский адрес", region="ru-ru")

    assert len(results) == 1
    assert results[0]["url"] == "https://cian.ru/x"
    assert mock_ddgs.text.call_count == 2
    assert mock_ddgs.text.call_args_list[1].kwargs["backend"] == "auto"


def test_client_returns_empty_when_all_backends_fail(monkeypatch):
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = DDGSException("No results found.")
    monkeypatch.setattr("interior_studio.web.client.DDGS", lambda: mock_ddgs)

    results = DuckDuckGoClient().search("нет такого", region="ru-ru")

    assert results == []
    assert mock_ddgs.text.call_count == 2


def test_client_propagates_non_empty_ddg_errors(monkeypatch):
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = RuntimeError("network down")
    monkeypatch.setattr("interior_studio.web.client.DDGS", lambda: mock_ddgs)

    with pytest.raises(RuntimeError, match="network down"):
        DuckDuckGoClient().search("тест")
