"""Tool calling: web search cascade (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools
from interior_studio.services import project_service, user_context
from tests.interior_studio.test_tool_calling import _tool_call


def _empty_knowledge_store():
    store = MagicMock()
    store.search.return_value = []
    return store


def _run_first_tool(db_session, user_id: int, query: str, tool_name: str, tool_args: dict):
    from interior_studio.services.user_context import upsert_user

    upsert_user(db_session, user_id)
    db_session.commit()

    tools = make_tools(db_session, user_id)
    prompt = build_system_prompt(user_id)

    first = _tool_call(tool_name, tool_args)
    final = AIMessage(content="Готово.")

    mock_llm = MagicMock()
    mock_bound = MagicMock()
    mock_bound.invoke.side_effect = [first, final]
    mock_llm.bind_tools.return_value = mock_bound
    mock_llm.invoke.return_value = AIMessage(content="размышляю")

    with (
        patch("interior_studio.agent.graph.create_chat_llm", return_value=mock_llm),
        patch("interior_studio.knowledge.search.KnowledgeStore", return_value=_empty_knowledge_store()),
        patch(
            "interior_studio.agent.tools.web_search.search_web",
            return_value=json.dumps(
                {
                    "ok": True,
                    "query": "web",
                    "results": [
                        {
                            "title": "ISP",
                            "url": "https://example.com/isp",
                            "snippet": "Ростелеком.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ),
    ):
        agent = create_studio_agent(tools, prompt)
        agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={"recursion_limit": 10},
        )

    return first.tool_calls[0]


def _run_tool_sequence(db_session, user_id: int, query: str, llm_steps: list[AIMessage]) -> list[str]:
    """Запускает агента с цепочкой mock-ответов LLM; возвращает имена вызванных tools."""
    from interior_studio.services.user_context import upsert_user

    upsert_user(db_session, user_id)
    db_session.commit()

    tools = make_tools(db_session, user_id)
    prompt = build_system_prompt(user_id)

    mock_llm = MagicMock()
    mock_bound = MagicMock()
    mock_bound.invoke.side_effect = llm_steps
    mock_llm.bind_tools.return_value = mock_bound
    mock_llm.invoke.return_value = AIMessage(content="размышляю")

    with (
        patch("interior_studio.agent.graph.create_chat_llm", return_value=mock_llm),
        patch("interior_studio.knowledge.search.KnowledgeStore", return_value=_empty_knowledge_store()),
        patch(
            "interior_studio.agent.tools.web_search.search_web",
            return_value=json.dumps(
                {
                    "ok": True,
                    "query": "web",
                    "results": [
                        {
                            "title": "ISP",
                            "url": "https://example.com/isp",
                            "snippet": "Ростелеком.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ),
    ):
        agent = create_studio_agent(tools, prompt)
        result = agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={"recursion_limit": 10},
        )

    tool_names: list[str] = []
    for msg in result["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tool_names.extend(tc["name"] for tc in msg.tool_calls)
    return tool_names


@pytest.mark.parametrize(
    "query",
    [
        "Найди в интернете аналоги плитки Kerama Marazzi 60x60",
        "Загугли норму освещённости для кухни",
        "Поищи в сети провайдеров интернета в ЖК Символ",
    ],
)
def test_explicit_web_calls_search_web_first(db_session, query):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    tc = _run_first_tool(db_session, 111111111, query, "search_web", {"query": "тестовый web запрос"})
    assert tc["name"] == "search_web"


def test_cascade_knowledge_then_web(db_session):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    steps = [
        _tool_call("search_project_knowledge", {"query": "интернет провайдеры ЖК"}),
        _tool_call("search_web", {"query": "интернет провайдеры ЖК Шкиперский"}),
        AIMessage(content="Провайдеры: Ростелеком. Источник: https://example.com/isp"),
    ]
    tool_names = _run_tool_sequence(
        db_session,
        111111111,
        "Какой интернет есть в ЖК Шкиперский?",
        steps,
    )
    assert tool_names == ["search_project_knowledge", "search_web"]


def test_internal_fact_empty_rag_no_web(db_session):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    steps = [
        _tool_call("search_project_knowledge", {"query": "цвет дверей"}),
        AIMessage(content="По документам проекта этого не нашёл."),
    ]
    tool_names = _run_tool_sequence(
        db_session,
        111111111,
        "Какой цвет дверей по Шкиперскому?",
        steps,
    )
    assert tool_names == ["search_project_knowledge"]
    assert "search_web" not in tool_names


def test_create_task_about_web_no_search(db_session):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    tc = _run_first_tool(
        db_session,
        111111111,
        "Создай задачу узнать какой интернет в ЖК до пятницы",
        "create_tasks",
        {
            "tasks": [
                {
                    "title": "Узнать интернет в ЖК",
                    "due_date": "2026-07-04",
                }
            ]
        },
    )
    assert tc["name"] == "create_tasks"
    assert tc["name"] != "search_web"


def test_list_tasks_no_search_web(db_session):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    tc = _run_first_tool(
        db_session,
        111111111,
        "Мои задачи на неделю",
        "list_tasks",
        {"week_only": True, "mine_only": True},
    )
    assert tc["name"] == "list_tasks"
    assert tc["name"] != "search_web"


def test_prompt_contains_web_rules():
    prompt = build_system_prompt(111111111)
    assert "search_web" in prompt
    assert "найди в интернете" in prompt.lower()
    assert "загугли" in prompt.lower()
    assert "поищи в сети" in prompt.lower()
    assert "Источник: {url}" in prompt
