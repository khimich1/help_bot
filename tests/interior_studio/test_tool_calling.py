"""Тесты tool calling: 11 кейсов из спеки §12 (mock LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import sessionmaker

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools
from interior_studio.bot.disambiguation import (
    DisambiguationKind,
    resolve_project_disambiguation,
)
from interior_studio.bot.main import BotRuntime, handle_text_message, pre_agent_disambiguation_hook
from interior_studio.bot.session import SessionStore
from interior_studio.services import project_service, user_context


def _tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="Выполняю действие.",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": "call_test_1",
                "type": "tool_call",
            }
        ],
    )


def _run_agent_with_mock_tool(db_session, user_id: int, query: str, tool_name: str, tool_args: dict):
    """Запускает агента с mock LLM, возвращающим один tool call."""
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

    with patch("interior_studio.agent.graph.create_chat_llm", return_value=mock_llm):
        agent = create_studio_agent(tools, prompt)
        agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={"recursion_limit": 10},
        )

    first_call = mock_bound.invoke.call_args_list[0][0][0]
    last_ai = None
    for msg in reversed(first_call):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai = msg
            break
    assert mock_bound.invoke.called
    assert first.tool_calls[0]["name"] == tool_name
    return first.tool_calls[0]


@pytest.mark.parametrize(
    "query,tool_name,expected_args",
    [
        (
            "По Ивановым заказать плитку",
            "create_tasks",
            {"project_id": 1, "tasks": [{"title": "Заказать плитку"}]},
        ),
        (
            "Работаем по Петровым",
            "set_active_project",
            {"project_id": 2},
        ),
        (
            "Что у меня на неделе?",
            "list_tasks",
            {"week_only": True, "mine_only": True},
        ),
        (
            "Что просрочено?",
            "list_tasks",
            {"overdue": True},
        ),
        (
            "Плитку заказали",
            "complete_task",
            {"task_id": 1},
        ),
        (
            "Новый проект Сидоровы",
            "create_project",
            {"name": "Сидоровы"},
        ),
        (
            "Покажи все проекты",
            "list_projects",
            {},
        ),
    ],
    ids=[
        "create_tasks_by_project",
        "set_active_project",
        "list_tasks_week",
        "list_tasks_overdue",
        "complete_task",
        "create_project",
        "list_projects",
    ],
)
def test_tool_calling_cases_1_to_7(db_session, query, tool_name, expected_args):
    p1 = project_service.create_project(db_session, "Ивановы")
    p2 = project_service.create_project(db_session, "Петровы")
    db_session.commit()

    args = dict(expected_args)
    if tool_name == "create_tasks" and args.get("project_id") == 1:
        args["project_id"] = p1.id
    if tool_name == "set_active_project" and args.get("project_id") == 2:
        args["project_id"] = p2.id

    tc = _run_agent_with_mock_tool(db_session, 111111111, query, tool_name, args)
    assert tc["name"] == tool_name
    for key, value in expected_args.items():
        if key == "project_id" and value in (1, 2):
            continue
        assert tc["args"].get(key) == value


def test_tool_calling_batch_three_tasks_one_call(db_session):
    project = project_service.create_project(db_session, "Ивановы")
    db_session.commit()

    tasks = [
        {"title": "Заказать плитку"},
        {"title": "Уточнить срок у поставщика", "assignee_user_id": 111111111},
        {"title": "Скинуть варианты света", "due_date": "2026-07-04"},
    ]
    tc = _run_agent_with_mock_tool(
        db_session,
        222222222,
        "По Ивановым — плитку, Сеня уточнит срок, до пятницы варианты света",
        "create_tasks",
        {"project_id": project.id, "tasks": tasks},
    )
    assert tc["name"] == "create_tasks"
    assert len(tc["args"]["tasks"]) == 3


def test_tool_calling_active_project_without_name(db_session):
    project = project_service.create_project(db_session, "Ивановы")
    user_context.set_active_project(db_session, 111111111, project.id)
    db_session.commit()

    tc = _run_agent_with_mock_tool(
        db_session,
        111111111,
        "Добавь задачу заказать краску",
        "create_tasks",
        {"project_id": project.id, "tasks": [{"title": "Заказать краску"}]},
    )
    assert tc["args"]["project_id"] == project.id


@pytest.mark.asyncio
async def test_tool_calling_ambiguous_text_no_agent(db_engine):
    """Кейс 10: неясный проект (текст) → кнопки, без tool до выбора."""
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    with factory() as db:
        project_service.create_project(db, "Ивановы")
        project_service.create_project(db, "Ивановы дача")
        db.commit()

    mock_agent = MagicMock()
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=lambda db, uid: mock_agent,
    )

    update = MagicMock()
    update.effective_user = MagicMock(id=111111111)
    update.message = MagicMock()
    update.message.text = "По Ивановым заказать плитку"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot_data = {"runtime": runtime}
    context.user_data = {}

    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]):
        await handle_text_message(
            update, context, pre_agent_hook=pre_agent_disambiguation_hook
        )

    mock_agent.invoke.assert_not_called()
    assert update.message.reply_text.await_args.kwargs.get("reply_markup") is not None

    with factory() as db:
        result = resolve_project_disambiguation(
            db, 111111111, "По Ивановым заказать плитку", is_voice=False
        )
    assert result.kind == DisambiguationKind.AMBIGUOUS_TEXT


def test_tool_calling_ambiguous_voice_text_question(db_session):
    """Кейс 11: неясный проект (голос) → текстовый вопрос, без tool."""
    project_service.create_project(db_session, "Ивановы")
    project_service.create_project(db_session, "Ивановы дача")
    db_session.commit()

    result = resolve_project_disambiguation(
        db_session,
        222222222,
        "По Ивановым заказать плитку",
        is_voice=True,
    )
    assert result.kind == DisambiguationKind.AMBIGUOUS_VOICE
    assert result.candidates is not None
    assert len(result.candidates) == 2
