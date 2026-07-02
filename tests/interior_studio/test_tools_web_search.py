"""Тесты tool search_web."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from interior_studio.agent.tools import make_tools
from interior_studio.agent.tools.web_search import search_web_impl


def test_search_web_impl_delegates_to_service(monkeypatch):
    mock_search = MagicMock(
        return_value=json.dumps(
            {"ok": True, "query": "тест", "results": []},
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("interior_studio.agent.tools.web_search.search_web", mock_search)

    raw = search_web_impl(None, 111111111, "тест", max_results=3)
    data = json.loads(raw)

    assert data["ok"] is True
    mock_search.assert_called_once_with("тест", max_results=3)


def test_make_tools_includes_search_web(db_session):
    tools = make_tools(db_session, 111111111)
    names = [t.name for t in tools]

    assert "search_web" in names
    assert names.index("search_project_knowledge") < names.index("search_web")
    assert len(tools) == 9


def test_search_web_tool_schema(db_session):
    tools = make_tools(db_session, 111111111)
    tool = next(t for t in tools if t.name == "search_web")

    assert "интернете" in tool.description.lower()
    assert tool.args_schema is not None
    schema = tool.args_schema.model_json_schema()
    assert "query" in schema["properties"]
    assert "max_results" in schema["properties"]
