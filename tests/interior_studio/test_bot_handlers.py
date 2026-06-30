"""Тесты Telegram handlers (mock Update/Context)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import sessionmaker
from telegram import Update, User

from interior_studio.bot.main import BotRuntime, handle_text_message, is_user_allowed
from interior_studio.bot.session import SessionStore
from interior_studio.db.models import User as DbUser
from interior_studio.services.user_context import upsert_user


def _make_update(user_id: int, text: str) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Test")
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_user = user
    update.message = message
    return update


@pytest.fixture
def bot_runtime(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            HumanMessage(content="Покажи проекты"),
            AIMessage(content="Вот активные проекты."),
        ]
    }

    def agent_factory(db, user_id):
        return mock_agent

    return BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=agent_factory,
    )


@pytest.mark.asyncio
async def test_non_whitelisted_user_ignored(bot_runtime):
    update = _make_update(user_id=999999999, text="Привет")
    context = MagicMock()
    context.bot_data = {"runtime": bot_runtime}
    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111, 222222222]):
        await handle_text_message(update, context)

    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_whitelisted_text_invokes_agent_and_replies(bot_runtime):
    update = _make_update(user_id=111111111, text="Покажи проекты")
    context = MagicMock()
    context.bot_data = {"runtime": bot_runtime}
    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111, 222222222]):
        await handle_text_message(update, context)

    update.message.reply_text.assert_awaited_once_with("Вот активные проекты.")
    history = bot_runtime.session_store.get(111111111).messages
    assert len(history) == 2


@pytest.mark.asyncio
async def test_first_message_upserts_user(db_session, bot_runtime):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    bot_runtime.db_factory = factory

    update = _make_update(user_id=111111111, text="Привет")
    context = MagicMock()
    context.bot_data = {"runtime": bot_runtime}
    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]):
        await handle_text_message(update, context)

    user = db_session.get(DbUser, 111111111)
    assert user is not None
    assert user.display_name == "Сеня"


def test_session_history_trimmed_to_20(bot_runtime):
    store = bot_runtime.session_store
    user_id = 111111111
    msgs = [HumanMessage(content=f"msg-{i}") for i in range(25)]
    store.append_messages(user_id, msgs)
    assert len(store.get(user_id).messages) == 20
    assert store.get(user_id).messages[0].content == "msg-5"


def test_is_user_allowed_respects_config():
    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111, 222]):
        assert is_user_allowed(111) is True
        assert is_user_allowed(333) is False
