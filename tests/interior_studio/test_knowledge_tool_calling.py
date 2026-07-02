"""Tool calling: knowledge search vs операционные запросы (mock LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools
from interior_studio.services import project_service, user_context
from tests.interior_studio.test_tool_calling import _tool_call


def _run_mock(db_session, user_id: int, query: str, tool_name: str, tool_args: dict):
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

    mock_store = MagicMock()
    mock_store.search.return_value = [
        {
            "text": "Тестовый фрагмент документа.",
            "source_path": "Исходные материалы/Общее бриф.pdf",
            "doc_type": "brief",
            "stage": "Исходные материалы",
            "room": None,
            "score": 0.9,
        }
    ]

    with (
        patch("interior_studio.agent.graph.create_chat_llm", return_value=mock_llm),
        patch("interior_studio.knowledge.search.KnowledgeStore", return_value=mock_store),
    ):
        agent = create_studio_agent(tools, prompt)
        agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={"recursion_limit": 10},
        )

    return first.tool_calls[0]


@pytest.mark.parametrize(
    "query,expected_tool",
    [
        ("По Шкиперскому какой цвет дверей?", "search_project_knowledge"),
        ("Что в брифе про кухню?", "search_project_knowledge"),
        ("Напомни пожелания Вики по гардеробной", "search_project_knowledge"),
        ("Закажи плитку в мастер-с/у как договаривались", "search_project_knowledge"),
    ],
)
def test_knowledge_queries_call_search_first(db_session, query, expected_tool):
    project = project_service.create_project(db_session, "ЖК Шкиперский")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    tc = _run_mock(
        db_session,
        111111111,
        query,
        expected_tool,
        {"query": "тестовый запрос"},
    )
    assert tc["name"] == expected_tool


@pytest.mark.parametrize(
    "query,expected_tool,expected_args",
    [
        ("Мои задачи на неделю", "list_tasks", {"week_only": True, "mine_only": True}),
        ("Что просрочено?", "list_tasks", {"overdue": True}),
        ("Работаем по Петровым", "set_active_project", {"project_id": 2}),
        ("Покажи все проекты", "list_projects", {}),
    ],
)
def test_operational_queries_skip_search(db_session, query, expected_tool, expected_args):
    p1 = project_service.create_project(db_session, "ЖК Шкиперский")
    p2 = project_service.create_project(db_session, "Петровы")
    user_context.set_active_project(db_session, 111111111, p1.id)
    db_session.commit()

    args = dict(expected_args)
    if expected_tool == "set_active_project":
        args["project_id"] = p2.id

    tc = _run_mock(db_session, 111111111, query, expected_tool, args)
    assert tc["name"] == expected_tool
    assert tc["name"] != "search_project_knowledge"
