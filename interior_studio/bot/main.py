"""Telegram-бот: long polling, whitelist, текстовые и голосовые сообщения."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from interior_studio.agent.graph import create_studio_agent
from interior_studio.agent.prompt import build_system_prompt
from interior_studio.agent.tools import make_tools
from interior_studio.bot.disambiguation import (
    DisambiguationKind,
    build_project_keyboard,
    format_text_disambiguation_question,
    format_voice_disambiguation_question,
    parse_callback_project_id,
    resolve_project_disambiguation,
    resolve_project_from_user_reply,
)
from interior_studio.bot.session import SessionStore
from interior_studio.bot.voice import WHISPER_ERROR_MESSAGE, transcribe_telegram_voice
from interior_studio.config import ALLOWED_USER_IDS
from interior_studio.db.connection import create_db_engine, create_session_factory, init_schema
from interior_studio.scheduler.jobs import setup_scheduler
from interior_studio.services.user_context import set_active_project, upsert_user

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


@dataclass
class BotRuntime:
    """Зависимости бота для handlers и тестов."""

    session_store: SessionStore
    db_factory: sessionmaker[Session]
    agent_factory: Callable[[Session, int], object] | None = None

    def create_agent(self, db: Session, user_id: int):
        if self.agent_factory:
            return self.agent_factory(db, user_id)
        tools = make_tools(db, user_id)
        prompt = build_system_prompt(user_id)
        return create_studio_agent(tools, prompt)


def is_user_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS


def extract_agent_reply(result_messages: list) -> str:
    """Берёт последний текстовый ответ агента без tool_calls."""
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return str(msg.content)
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return "Готово."


def invoke_agent(
    runtime: BotRuntime,
    db: Session,
    user_id: int,
    history: list,
    user_text: str,
) -> tuple[str, list]:
    """Вызывает ReAct-агента и возвращает ответ + обновлённую историю."""
    agent = runtime.create_agent(db, user_id)
    messages = list(history)
    messages.append(HumanMessage(content=user_text))
    result = agent.invoke({"messages": messages}, config={"recursion_limit": 10})
    db.commit()
    reply = extract_agent_reply(result["messages"])
    return reply, result["messages"]


async def pre_agent_disambiguation_hook(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    runtime: BotRuntime,
    db: Session,
    user_id: int,
    text: str,
    *,
    is_voice: bool = False,
) -> bool:
    """Проверяет disambiguation до вызова агента. True = обработано, агент не нужен."""
    session_store = runtime.session_store
    pending = session_store.get_pending(user_id)

    if pending is not None:
        project = resolve_project_from_user_reply(
            db, text, pending.candidate_project_ids
        )
        if project is None:
            await update.message.reply_text(
                "Не поняла, какой проект ты имеешь в виду. Напиши точное название."
            )
            return True
        set_active_project(db, user_id, project.id)
        db.commit()
        text = pending.original_text
        session_store.clear_pending(user_id)
    else:
        result = resolve_project_disambiguation(
            db, user_id, text, is_voice=is_voice
        )
        if result.kind == DisambiguationKind.AMBIGUOUS_TEXT:
            session_store.set_pending(
                user_id,
                original_text=text,
                candidate_project_ids=[c.id for c in result.candidates or []],
                is_voice=False,
            )
            keyboard = build_project_keyboard(result.candidates or [])
            await update.message.reply_text(
                format_text_disambiguation_question(result.candidates or []),
                reply_markup=keyboard,
            )
            return True
        if result.kind == DisambiguationKind.AMBIGUOUS_VOICE:
            session_store.set_pending(
                user_id,
                original_text=text,
                candidate_project_ids=[c.id for c in result.candidates or []],
                is_voice=True,
            )
            await update.message.reply_text(
                format_voice_disambiguation_question(result.candidates or [])
            )
            return True
        if result.kind == DisambiguationKind.RESOLVED and result.project:
            set_active_project(db, user_id, result.project.id)
            db.commit()

    context.user_data["_agent_text"] = text
    return False


async def _continue_after_project_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    runtime: BotRuntime,
    user_id: int,
    original_text: str,
    *,
    reply_message=None,
) -> None:
    """Вызывает агента после выбора проекта и отправляет ответ."""
    user_session = runtime.session_store.get(user_id)
    with runtime.db_factory() as db:
        reply, new_history = invoke_agent(
            runtime,
            db,
            user_id,
            user_session.messages,
            original_text,
        )
        runtime.session_store.append_messages(
            user_id, new_history[len(user_session.messages) :]
        )

    target = reply_message or update.message
    if target is not None:
        await target.reply_text(reply)


async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик inline-кнопок выбора проекта."""
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    if not is_user_allowed(user_id):
        return

    project_id = parse_callback_project_id(query.data)
    if project_id is None:
        await query.answer()
        return

    runtime: BotRuntime = context.bot_data["runtime"]
    pending = runtime.session_store.get_pending(user_id)
    if pending is None or project_id not in pending.candidate_project_ids:
        await query.answer("Выбор устарел, напиши запрос заново.")
        return

    await query.answer()

    with runtime.db_factory() as db:
        set_active_project(db, user_id, project_id)
        db.commit()

    original_text = pending.original_text
    runtime.session_store.clear_pending(user_id)

    await _continue_after_project_choice(
        update,
        context,
        runtime,
        user_id,
        original_text,
        reply_message=query.message,
    )


async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    pre_agent_hook: Callable | None = None,
    post_agent_hook: Callable | None = None,
) -> None:
    """Обработчик текстовых сообщений."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    if not is_user_allowed(user_id):
        logger.info("Ignored message from non-whitelisted user_id=%s", user_id)
        return

    runtime: BotRuntime = context.bot_data["runtime"]
    session_store = runtime.session_store
    user_session = session_store.get(user_id)
    user_session.last_message_is_voice = False
    text = update.message.text.strip()

    with runtime.db_factory() as db:
        upsert_user(db, user_id)
        db.commit()

        if pre_agent_hook is not None:
            handled = await pre_agent_hook(
                update, context, runtime, db, user_id, text, is_voice=False
            )
            if handled:
                return

        agent_text = context.user_data.pop("_agent_text", text)
        reply, new_history = invoke_agent(
            runtime,
            db,
            user_id,
            user_session.messages,
            agent_text,
        )
        session_store.append_messages(user_id, new_history[len(user_session.messages) :])

    if post_agent_hook is not None:
        await post_agent_hook(update, context, reply)

    await update.message.reply_text(reply)


async def handle_voice_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик голосовых сообщений: Whisper → тот же flow, что и текст."""
    if not update.effective_user or not update.message or not update.message.voice:
        return

    user_id = update.effective_user.id
    if not is_user_allowed(user_id):
        logger.info("Ignored voice from non-whitelisted user_id=%s", user_id)
        return

    runtime: BotRuntime = context.bot_data["runtime"]
    session_store = runtime.session_store
    user_session = session_store.get(user_id)
    user_session.last_message_is_voice = True

    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    transcript = await transcribe_telegram_voice(tg_file)

    if not transcript:
        await update.message.reply_text(WHISPER_ERROR_MESSAGE)
        return

    with runtime.db_factory() as db:
        upsert_user(db, user_id)
        db.commit()

        handled = await pre_agent_disambiguation_hook(
            update,
            context,
            runtime,
            db,
            user_id,
            transcript,
            is_voice=True,
        )
        if handled:
            return

        agent_text = context.user_data.pop("_agent_text", transcript)
        reply, new_history = invoke_agent(
            runtime,
            db,
            user_id,
            user_session.messages,
            agent_text,
        )
        session_store.append_messages(user_id, new_history[len(user_session.messages) :])

    await update.message.reply_text(reply)


async def _on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_voice_message(update, context)


async def _on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_text_message(update, context, pre_agent_hook=pre_agent_disambiguation_hook)


def build_application(
    runtime: BotRuntime | None = None,
    token: str | None = None,
    *,
    with_scheduler: bool = False,
) -> Application:
    """Собирает Application с handlers (scheduler опционально)."""
    db_factory = runtime.db_factory if runtime else None
    if runtime is None:
        engine = create_db_engine()
        init_schema(engine)
        db_factory = create_session_factory(engine)
        runtime = BotRuntime(
            session_store=SessionStore(),
            db_factory=db_factory,
        )

    async def _post_init(app: Application) -> None:
        if with_scheduler and db_factory is not None:
            app.bot_data["scheduler"] = setup_scheduler(app, db_factory)

    app = (
        Application.builder()
        .token(token or TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )
    app.bot_data["runtime"] = runtime
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text))
    app.add_handler(MessageHandler(filters.VOICE, _on_voice))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    return app


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        level=logging.INFO,
    )
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан в .env")

    engine = create_db_engine()
    init_schema(engine)
    runtime = BotRuntime(
        session_store=SessionStore(),
        db_factory=create_session_factory(engine),
    )
    app = build_application(runtime=runtime, with_scheduler=True)
    logger.info("Starting Interior Studio bot (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
