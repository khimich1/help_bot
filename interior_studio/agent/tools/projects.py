"""Tools для проектов."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interior_studio.services import project_service, user_context


class ListProjectsArgs(BaseModel):
    status: str = Field(default="active", description="Фильтр статуса: active или archived")


class CreateProjectArgs(BaseModel):
    name: str = Field(description="Название нового проекта (фамилия клиента)")


class SetActiveProjectArgs(BaseModel):
    project_id: int = Field(description="ID проекта, который станет активным")


LIST_PROJECTS_SCHEMA = {
    "description": "Получить список проектов студии.",
    "args_schema": ListProjectsArgs,
}

CREATE_PROJECT_SCHEMA = {
    "description": "Создать новый проект (клиента).",
    "args_schema": CreateProjectArgs,
}

GET_ACTIVE_PROJECT_SCHEMA = {
    "description": "Получить текущий активный проект пользователя.",
    "args_schema": None,
}

SET_ACTIVE_PROJECT_SCHEMA = {
    "description": "Установить активный проект для текущего пользователя.",
    "args_schema": SetActiveProjectArgs,
}


def list_projects_impl(session: Session, user_id: int, status: str = "active") -> str:
    projects = project_service.list_projects(session, status=status)
    return json.dumps(
        {"projects": [p.model_dump() for p in projects]},
        ensure_ascii=False,
    )


def create_project_impl(session: Session, user_id: int, name: str) -> str:
    try:
        project = project_service.create_project(session, name)
        user_context.set_active_project(session, user_id, project.id)
        return json.dumps(project.model_dump(), ensure_ascii=False)
    except project_service.ProjectAlreadyExistsError as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)
    except ValueError as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def get_active_project_impl(session: Session, user_id: int) -> str:
    active = user_context.get_active_project(session, user_id)
    return json.dumps(active.model_dump(), ensure_ascii=False)


def set_active_project_impl(session: Session, user_id: int, project_id: int) -> str:
    ok, err = user_context.set_active_project(session, user_id, project_id)
    if not ok:
        return json.dumps({"ok": False, "message": err}, ensure_ascii=False)
    project = project_service.get_project_by_id(session, project_id)
    return json.dumps(
        {"ok": True, "project": project.model_dump() if project else None},
        ensure_ascii=False,
    )
