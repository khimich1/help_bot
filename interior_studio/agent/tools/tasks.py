"""Tools для задач."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interior_studio.schemas.task import TaskInput
from interior_studio.services import task_service


class TaskItemArgs(BaseModel):
    title: str = Field(description="Краткое название задачи")
    assignee_user_id: int | None = Field(default=None, description="ID исполнителя (Сеня/Рита)")
    due_date: str | None = Field(default=None, description="Дедлайн YYYY-MM-DD")
    notes: str | None = Field(default=None, description="Дополнительные заметки")


class CreateTasksArgs(BaseModel):
    project_id: int = Field(description="ID проекта")
    tasks: list[TaskItemArgs] = Field(description="Список задач для создания за один вызов")


class ListTasksArgs(BaseModel):
    project_id: int | None = Field(default=None, description="Фильтр по проекту")
    mine_only: bool = Field(default=False, description="Только мои задачи (assignee или создатель)")
    status: str | None = Field(default="open", description="Статус: open или done")
    overdue: bool = Field(default=False, description="Только просроченные")
    week_only: bool = Field(default=False, description="Задачи на текущую неделю")


class CompleteTaskArgs(BaseModel):
    task_id: int = Field(description="ID задачи для закрытия")


CREATE_TASKS_SCHEMA = {
    "description": (
        "Создать одну или несколько задач в проекте. "
        "Для голосового batch — один вызов со всеми задачами."
    ),
    "args_schema": CreateTasksArgs,
}

LIST_TASKS_SCHEMA = {
    "description": "Список задач с фильтрами: проект, мои, просроченные, на неделю.",
    "args_schema": ListTasksArgs,
}

COMPLETE_TASK_SCHEMA = {
    "description": "Отметить задачу выполненной по task_id.",
    "args_schema": CompleteTaskArgs,
}


def create_tasks_impl(
    session: Session,
    user_id: int,
    project_id: int,
    tasks: list[TaskItemArgs | dict],
) -> str:
    try:
        parsed = [
            t if isinstance(t, TaskItemArgs) else TaskItemArgs.model_validate(t)
            for t in tasks
        ]
        inputs = [
            TaskInput(
                title=t.title,
                assignee_user_id=t.assignee_user_id,
                due_date=t.due_date,
                notes=t.notes,
            )
            for t in parsed
        ]
        result = task_service.create_tasks(session, project_id, inputs, created_by=user_id)
        return json.dumps(
            {
                "created": [t.model_dump() for t in result.created],
                "count": result.count,
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def list_tasks_impl(
    session: Session,
    user_id: int,
    project_id: int | None = None,
    mine_only: bool = False,
    status: str | None = "open",
    overdue: bool = False,
    week_only: bool = False,
) -> str:
    tasks = task_service.list_tasks(
        session,
        user_id,
        project_id=project_id,
        mine_only=mine_only,
        status=status,
        overdue=overdue,
        week_only=week_only,
    )
    return json.dumps({"tasks": [t.model_dump() for t in tasks]}, ensure_ascii=False)


def complete_task_impl(session: Session, user_id: int, task_id: int) -> str:
    result = task_service.complete_task(session, user_id, task_id)
    payload = {
        "ok": result.ok,
        "task": result.task.model_dump() if result.task else None,
        "message": result.message,
    }
    return json.dumps(payload, ensure_ascii=False)
