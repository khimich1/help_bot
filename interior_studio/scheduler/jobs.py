"""Утренний дайджест и напоминания за день до дедлайна."""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot

from interior_studio.config import ALLOWED_USER_IDS
from interior_studio.db.models import Project, SentReminder, Task
from interior_studio.services import task_service

logger = logging.getLogger(__name__)

REMINDER_TYPE_DEADLINE_1D = "deadline_1d"


def format_task_line(task, project_name: str) -> str:
    parts = [f"• {task.title} ({project_name})"]
    if task.due_date:
        parts.append(f" — до {task.due_date}")
    return "".join(parts)


def build_morning_digest_text(session: Session, user_id: int) -> str | None:
    """Формирует текст дайджеста или None, если задач нет."""
    overdue = task_service.list_tasks(session, user_id, overdue=True)
    today = task_service.list_tasks_today(session, user_id)
    week = task_service.list_tasks(session, user_id, week_only=True)

    if not overdue and not today and not week:
        return None

    lines = ["☀️ Доброе утро! Твой дайджест:"]

    def _section(title: str, tasks: list) -> None:
        if not tasks:
            return
        lines.append(f"\n{title}:")
        for t in tasks:
            project = session.get(Project, t.project_id)
            name = project.name if project else f"#{t.project_id}"
            lines.append(format_task_line(t, name))

    _section("🔴 Просрочено", overdue)
    _section("📅 Сегодня", today)
    _section("📆 На неделе", week)

    return "\n".join(lines)


async def morning_digest(bot: Bot, db_factory: sessionmaker[Session]) -> None:
    """Отправляет утренний дайджест каждому пользователю из whitelist."""
    with db_factory() as session:
        for user_id in ALLOWED_USER_IDS:
            text = build_morning_digest_text(session, user_id)
            if not text:
                continue
            try:
                await bot.send_message(chat_id=user_id, text=text)
            except Exception:
                logger.exception("Failed to send morning digest to user_id=%s", user_id)


def _reminder_already_sent(session: Session, task_id: int) -> bool:
    existing = session.scalars(
        select(SentReminder).where(
            SentReminder.task_id == task_id,
            SentReminder.reminder_type == REMINDER_TYPE_DEADLINE_1D,
        )
    ).first()
    return existing is not None


def _record_reminder_sent(session: Session, task_id: int) -> None:
    session.add(
        SentReminder(task_id=task_id, reminder_type=REMINDER_TYPE_DEADLINE_1D)
    )
    session.flush()


def format_deadline_reminder(task, project_name: str) -> str:
    return (
        f"⏰ Завтра дедлайн: «{task.title}» по проекту {project_name}"
        + (f" (до {task.due_date})" if task.due_date else "")
    )


def get_deadline_reminder_recipients(task) -> list[int]:
    """Assignee или оба дизайнера, если исполнитель не указан."""
    if task.assignee_user_id is not None:
        return [task.assignee_user_id]
    return list(ALLOWED_USER_IDS)


async def deadline_reminder(bot: Bot, db_factory: sessionmaker[Session]) -> None:
    """Напоминание за день до дедлайна — один раз per task."""
    with db_factory() as session:
        tasks = task_service.list_tasks_due_tomorrow(session)
        for task_out in tasks:
            if _reminder_already_sent(session, task_out.id):
                continue

            task = session.get(Task, task_out.id)
            if not task:
                continue

            project = session.get(Project, task.project_id)
            project_name = project.name if project else f"#{task.project_id}"
            text = format_deadline_reminder(task_out, project_name)
            recipients = get_deadline_reminder_recipients(task_out)

            sent_any = False
            for user_id in recipients:
                try:
                    await bot.send_message(chat_id=user_id, text=text)
                    sent_any = True
                except Exception:
                    logger.exception(
                        "Failed deadline reminder task_id=%s user_id=%s",
                        task_out.id,
                        user_id,
                    )

            if sent_any:
                _record_reminder_sent(session, task_out.id)

        session.commit()


def setup_scheduler(app, db_factory: sessionmaker[Session]):
    """Регистрирует cron jobs в AsyncIOScheduler (Europe/Moscow 09:00)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from zoneinfo import ZoneInfo

    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Moscow"))

    async def _run_morning_digest() -> None:
        await morning_digest(app.bot, db_factory)

    async def _run_deadline_reminder() -> None:
        await deadline_reminder(app.bot, db_factory)

    scheduler.add_job(
        _run_morning_digest,
        trigger="cron",
        hour=9,
        minute=0,
        id="morning_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_deadline_reminder,
        trigger="cron",
        hour=9,
        minute=0,
        id="deadline_reminder",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
