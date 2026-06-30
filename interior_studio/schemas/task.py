"""Схемы задач."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskInput(BaseModel):
    title: str = Field(min_length=1)
    assignee_user_id: int | None = None
    due_date: str | None = None
    notes: str | None = None


class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    notes: str | None = None
    status: str
    assignee_user_id: int | None = None
    created_by: int
    due_date: str | None = None
    completed_at: str | None = None


class CreateTasksResult(BaseModel):
    created: list[TaskOut]
    count: int


class CompleteTaskResult(BaseModel):
    ok: bool
    task: TaskOut | None = None
    message: str | None = None
