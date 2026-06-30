"""Тесты голосового pipeline (mock Whisper)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from interior_studio.bot.main import BotRuntime, handle_voice_message
from interior_studio.bot.session import SessionStore
from interior_studio.bot.voice import WHISPER_ERROR_MESSAGE, transcribe_audio_file


@pytest.mark.asyncio
async def test_voice_success_invokes_agent(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            __import__("langchain_core.messages", fromlist=["AIMessage"]).AIMessage(
                content="Задача создана."
            )
        ]
    }
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=lambda db, uid: mock_agent,
    )

    update = MagicMock()
    update.effective_user = MagicMock(id=111111111)
    update.message = MagicMock()
    update.message.voice = MagicMock(file_id="voice123")
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"runtime": runtime}
    context.user_data = {}
    context.bot.get_file = AsyncMock(return_value=MagicMock())

    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]), patch(
        "interior_studio.bot.main.transcribe_telegram_voice",
        new_callable=AsyncMock,
        return_value="По Ивановым заказать плитку",
    ), patch(
        "interior_studio.bot.main.pre_agent_disambiguation_hook",
        new_callable=AsyncMock,
        return_value=False,
    ):
        await handle_voice_message(update, context)

    mock_agent.invoke.assert_called_once()
    update.message.reply_text.assert_awaited_once_with("Задача создана.")
    assert runtime.session_store.get(111111111).last_message_is_voice is True


@pytest.mark.asyncio
async def test_voice_empty_transcript_shows_error(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=MagicMock(),
    )

    update = MagicMock()
    update.effective_user = MagicMock(id=111111111)
    update.message = MagicMock()
    update.message.voice = MagicMock(file_id="voice123")
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"runtime": runtime}
    context.bot.get_file = AsyncMock(return_value=MagicMock())

    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]), patch(
        "interior_studio.bot.main.transcribe_telegram_voice",
        new_callable=AsyncMock,
        return_value="",
    ):
        await handle_voice_message(update, context)

    update.message.reply_text.assert_awaited_once_with(WHISPER_ERROR_MESSAGE)


def test_transcribe_audio_file_returns_text():
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(
        text="  Привет  "
    )
    path = MagicMock()
    path.open.return_value.__enter__.return_value = MagicMock()

    with patch("interior_studio.bot.voice.Path") as mock_path_cls:
        mock_path_cls.return_value = path
        result = transcribe_audio_file(mock_client, path)

    assert result == "Привет"


@pytest.mark.asyncio
async def test_voice_ambiguous_triggers_disambiguation_not_agent(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    mock_agent = MagicMock()
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=factory,
        agent_factory=lambda db, uid: mock_agent,
    )

    update = MagicMock()
    update.effective_user = MagicMock(id=111111111)
    update.message = MagicMock()
    update.message.voice = MagicMock(file_id="voice123")
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"runtime": runtime}
    context.user_data = {}
    context.bot.get_file = AsyncMock(return_value=MagicMock())

    with patch("interior_studio.bot.main.ALLOWED_USER_IDS", [111111111]), patch(
        "interior_studio.bot.main.transcribe_telegram_voice",
        new_callable=AsyncMock,
        return_value="По Ивановым заказать плитку",
    ), patch(
        "interior_studio.bot.main.pre_agent_disambiguation_hook",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_hook:
        await handle_voice_message(update, context)

    mock_hook.assert_awaited_once()
    call_kwargs = mock_hook.await_args.kwargs
    assert call_kwargs.get("is_voice") is True
    mock_agent.invoke.assert_not_called()
