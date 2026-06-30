"""Схемы проектов."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectOut(BaseModel):
    id: int
    name: str
    status: str = "active"


class ActiveProjectOut(BaseModel):
    project_id: int | None
    name: str | None = None


class SetActiveProjectResult(BaseModel):
    ok: bool
    project: ProjectOut | None = None
    message: str | None = None
