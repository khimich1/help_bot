"""Тесты disambiguation (гибрид C)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from interior_studio.bot.disambiguation import (
    DisambiguationKind,
    build_project_keyboard,
    extract_project_hint,
    format_voice_disambiguation_question,
    parse_callback_project_id,
    resolve_project_disambiguation,
    resolve_project_from_user_reply,
)
from interior_studio.bot.main import (
    BotRuntime,
    handle_callback_query,
    handle_text_message,
    pre_agent_disambiguation_hook,
)
from interior_studio.bot.session import SessionStore
from interior_studio.services import project_service, user_context


def test_extract_project_hint_po_ivanovym():
    assert extract_project_hint("По Ивановым заказать плитку") == "Ивановым"


def test_ambiguous_text_returns_inline_candidates(db_session):
    project_service.create_project(db_session, "Ивановы")
    project_service.create_project(db_session, "Ивановы дача")
    db_session.commit()

    result = resolve_project_disambiguation(
        db_session, 111111111, "По Ивановым заказать плитку", is_voice=False
    )
    assert result.kind == DisambiguationKind.AMBIGUOUS_TEXT
    assert result.candidates is not None
    assert len(result.candidates) == 2


def test_active_project_skips_disambiguation(db_session):
    p1 = project_service.create_project(db_session, "Ивановы")
    project_service.create_project(db_session, "Ивановы дача")
    user_context.set_active_project(db_session, 111111111, p1.id)
    db_session.commit()

    result = resolve_project_disambiguation(
        db_session, 111111111, "По Ивановым заказать плитку"
    )
    assert result.kind == DisambiguationKind.RESOLVED
    assert result.project is not None
    assert result.project.id == p1.id


def test_ambiguous_voice_returns_text_question(db_session):
    project_service.create_project(db_session, "Ивановы")
    project_service.create_project(db_session, "Ивановы дача")
    db_session.commit()

    result = resolve_project_disambiguation(
        db_session, 111111111, "По Ивановым заказать плитку", is_voice=True
    )
    assert result.kind == DisambiguationKind.AMBIGUOUS_VOICE
    text = format_voice_disambiguation_question(result.candidates or [])
    assert "2 проекта" in text
    assert "Ивановы" in text


def test_build_project_keyboard_callback_data():
    from interior_studio.schemas.project import ProjectOut

    candidates = [
        ProjectOut(id=1, name="Ивановы", status="active"),
        ProjectOut(id=2, name="Ивановы дача", status="active"),
    ]
    keyboard = build_project_keyboard(candidates)
    assert len(keyboard.inline_keyboard) == 2
    assert keyboard.inline_keyboard[0][0].callback_data == "proj:1"


def test_parse_callback_project_id():
    assert parse_callback_project_id("proj:42") == 42
    assert parse_callback_project_id("other:42") is None


def test_resolve_project_from_user_reply(db_session):
    p1 = project_service.create_project(db_session, "Ивановы")
    p2 = project_service.create_project(db_session, "Ивановы дача")
    db_session.commit()

    chosen = resolve_project_from_user_reply(
        db_session, "Ивановы дача", [p1.id, p2.id]
    )
    assert chosen is not None
    assert chosen.id == p2.id


@pytest.mark.asyncio
async def test_text_ambiguous_shows_buttons_not_agent(db_engine):
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
    update.message.reply_text.assert_awaited_once()
    call_kwargs = update.message.reply_text.await_args
    assert call_kwargs.kwargs.get("reply_markup") is not None
    assert runtime.session_store.get_pending(111111111) is not None


@pytest.mark.asyncio
async def test_callback_continues_with_original_text(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    with factory() as db:
        p1 = project_service.create_project(db, "Ивановы")
        project_service.create_project(db, "Ивановы дача")
        db.commit()

    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            __import__("langchain_core.messages", fromlist=["AIMessage"]).AIMessage(
                content="Создала задачу."
            )
        ]
    }
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=lambda db, uid: mock_agent,
    )
    runtime.session_store.set_pending(
        111111111,
        original_text="По Ивановым заказать плитку",
        candidate_project_ids=[p1.id, 2],
        is_voice=False,
    )

    update = MagicMock()
    update.effective_user = MagicMock(id=111111111)
    update.callback_query = MagicMock()
    update.callback_query.data = "proj:1"
    update.callback_query.answer = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot_data = {"runtime": runtime}

    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]):
        await handle_callback_query(update, context)

    mock_agent.invoke.assert_called_once()
    invoke_messages = mock_agent.invoke.call_args[0][0]["messages"]
    assert invoke_messages[-1].content == "По Ивановым заказать плитку"
    update.callback_query.message.reply_text.assert_awaited_once_with("Создала задачу.")
