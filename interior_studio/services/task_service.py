"""Сервис задач."""

from __future__ import annotations

import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from interior_studio.db.models import Project, Task
from interior_studio.schemas.task import (
    CompleteTaskResult,
    CreateTasksResult,
    TaskInput,
    TaskOut,
)
from interior_studio.services.user_context import upsert_user


def _task_to_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        notes=task.notes,
        status=task.status,
        assignee_user_id=task.assignee_user_id,
        created_by=task.created_by,
        due_date=task.due_date,
        completed_at=task.completed_at,
    )


def create_tasks(
    session: Session,
    project_id: int,
    tasks: list[TaskInput | dict],
    created_by: int,
) -> CreateTasksResult:
    upsert_user(session, created_by)
    project = session.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    created: list[TaskOut] = []
    for raw in tasks:
        item = raw if isinstance(raw, TaskInput) else TaskInput.model_validate(raw)
        if item.assignee_user_id is not None:
            upsert_user(session, item.assignee_user_id)
        task = Task(
            project_id=project_id,
            title=item.title.strip(),
            notes=item.notes,
            assignee_user_id=item.assignee_user_id,
            created_by=created_by,
            due_date=item.due_date,
            status="open",
        )
        session.add(task)
        session.flush()
        created.append(_task_to_out(task))

    return CreateTasksResult(created=created, count=len(created))


def list_tasks(
    session: Session,
    user_id: int,
    project_id: int | None = None,
    mine_only: bool = False,
    status: str | None = "open",
    overdue: bool = False,
    week_only: bool = False,
) -> list[TaskOut]:
    upsert_user(session, user_id)
    today = datetime.date.today()
    stmt = select(Task)

    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if mine_only:
        stmt = stmt.where(
            or_(Task.assignee_user_id == user_id, Task.created_by == user_id)
        )
    if overdue:
        today_str = today.isoformat()
        stmt = stmt.where(
            Task.status == "open",
            Task.due_date.is_not(None),
            Task.due_date < today_str,
        )
    if week_only:
        week_end = (today + datetime.timedelta(days=7)).isoformat()
        today_str = today.isoformat()
        stmt = stmt.where(
            Task.due_date.is_not(None),
            Task.due_date >= today_str,
            Task.due_date <= week_end,
        )

    tasks = session.scalars(stmt.order_by(Task.due_date.nulls_last(), Task.id)).all()
    return [_task_to_out(t) for t in tasks]


def list_tasks_today(session: Session, user_id: int) -> list[TaskOut]:
    """Открытые задачи с дедлайном на сегодня."""
    upsert_user(session, user_id)
    today_str = datetime.date.today().isoformat()
    stmt = (
        select(Task)
        .where(
            Task.status == "open",
            Task.due_date == today_str,
        )
        .order_by(Task.due_date.nulls_last(), Task.id)
    )
    tasks = session.scalars(stmt).all()
    return [_task_to_out(t) for t in tasks]


def list_tasks_due_tomorrow(session: Session) -> list[TaskOut]:
    """Открытые задачи с дедлайном на завтра (для deadline_reminder)."""
    tomorrow_str = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    stmt = (
        select(Task)
        .where(Task.status == "open", Task.due_date == tomorrow_str)
        .order_by(Task.id)
    )
    tasks = session.scalars(stmt).all()
    return [_task_to_out(t) for t in tasks]


def complete_task(session: Session, user_id: int, task_id: int) -> CompleteTaskResult:
    upsert_user(session, user_id)
    task = session.get(Task, task_id)
    if not task:
        return CompleteTaskResult(ok=False, message=f"Task {task_id} not found")
    if task.status == "done":
        return CompleteTaskResult(ok=True, task=_task_to_out(task), message="Already completed")

    task.status = "done"
    task.completed_at = datetime.datetime.utcnow().isoformat(timespec="seconds")
    session.flush()
    return CompleteTaskResult(ok=True, task=_task_to_out(task))


def find_open_tasks_by_title_substring(
    session: Session, title_substring: str, project_id: int | None = None
) -> list[TaskOut]:
    """Поиск открытых задач по подстроке в title (для complete_task через агента)."""
    q = title_substring.strip().lower()
    stmt = select(Task).where(Task.status == "open")
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    tasks = session.scalars(stmt).all()
    matches = [t for t in tasks if q in t.title.lower()]
    return [_task_to_out(t) for t in matches]
