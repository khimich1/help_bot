"""Тесты scheduler: дайджест и deadline reminder."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from interior_studio.db.models import SentReminder
from interior_studio.scheduler.jobs import (
    REMINDER_TYPE_DEADLINE_1D,
    build_morning_digest_text,
    deadline_reminder,
    format_deadline_reminder,
    get_deadline_reminder_recipients,
    morning_digest,
)
from interior_studio.services import project_service, task_service
from interior_studio.schemas.task import TaskInput


def test_build_morning_digest_includes_sections(db_session):
    project = project_service.create_project(db_session, "Ивановы")
    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()

    task_service.create_tasks(
        db_session,
        project.id,
        [
            TaskInput(title="Просроченная", due_date=yesterday),
            TaskInput(title="На сегодня", due_date=today.isoformat()),
            TaskInput(title="На неделе", due_date=tomorrow),
        ],
        created_by=111111111,
    )
    db_session.commit()

    text = build_morning_digest_text(db_session, 111111111)
    assert text is not None
    assert "Просрочено" in text
    assert "Сегодня" in text
    assert "На неделе" in text
    assert "Просроченная" in text


def test_build_morning_digest_empty_returns_none(db_session):
    assert build_morning_digest_text(db_session, 111111111) is None


def test_get_deadline_reminder_recipients_with_assignee():
    task = MagicMock(assignee_user_id=222222222)
    assert get_deadline_reminder_recipients(task) == [222222222]


def test_get_deadline_reminder_recipients_without_assignee():
    task = MagicMock(assignee_user_id=None)
    with patch("interior_studio.scheduler.jobs.ALLOWED_USER_IDS", [111, 222]):
        assert get_deadline_reminder_recipients(task) == [111, 222]


@pytest.mark.asyncio
async def test_morning_digest_sends_to_users(db_session):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    project = project_service.create_project(db_session, "Петровы")
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    task_service.create_tasks(
        db_session,
        project.id,
        [TaskInput(title="Срочно", due_date=yesterday)],
        created_by=111111111,
    )
    db_session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("interior_studio.scheduler.jobs.ALLOWED_USER_IDS", [111111111, 222222222]):
        await morning_digest(bot, factory)

    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_deadline_reminder_sends_once(db_session):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    project = project_service.create_project(db_session, "Сидоровы")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    result = task_service.create_tasks(
        db_session,
        project.id,
        [TaskInput(title="Плитка", due_date=tomorrow, assignee_user_id=111111111)],
        created_by=222222222,
    )
    db_session.commit()
    task_id = result.created[0].id

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("interior_studio.scheduler.jobs.ALLOWED_USER_IDS", [111111111, 222222222]):
        await deadline_reminder(bot, factory)
        await deadline_reminder(bot, factory)

    bot.send_message.assert_awaited_once()
    reminder = db_session.scalars(
        __import__("sqlalchemy", fromlist=["select"]).select(SentReminder).where(
            SentReminder.task_id == task_id
        )
    ).first()
    assert reminder is not None
    assert reminder.reminder_type == REMINDER_TYPE_DEADLINE_1D


@pytest.mark.asyncio
async def test_deadline_reminder_without_assignee_notifies_both(db_session):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    project = project_service.create_project(db_session, "Козловы")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    task_service.create_tasks(
        db_session,
        project.id,
        [TaskInput(title="Свет", due_date=tomorrow)],
        created_by=111111111,
    )
    db_session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("interior_studio.scheduler.jobs.ALLOWED_USER_IDS", [111111111, 222222222]):
        await deadline_reminder(bot, factory)

    assert bot.send_message.await_count == 2


def test_format_deadline_reminder():
    task = MagicMock(title="Плитка", due_date="2026-07-01")
    text = format_deadline_reminder(task, "Ивановы")
    assert "Плитка" in text
    assert "Ивановы" in text
