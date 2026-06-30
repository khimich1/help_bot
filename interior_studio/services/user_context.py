"""Контекст пользователя: upsert, активный проект."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from interior_studio.config import DESIGNER_NAMES
from interior_studio.db.models import Project, User
from interior_studio.schemas.project import ActiveProjectOut


def upsert_user(session: Session, telegram_user_id: int) -> User:
    """Создаёт пользователя при первом обращении."""
    user = session.get(User, telegram_user_id)
    if user:
        return user
    display_name = DESIGNER_NAMES.get(telegram_user_id)
    user = User(telegram_user_id=telegram_user_id, display_name=display_name)
    session.add(user)
    session.flush()
    return user


def get_active_project(session: Session, user_id: int) -> ActiveProjectOut:
    upsert_user(session, user_id)
    user = session.get(User, user_id)
    if not user or not user.active_project_id:
        return ActiveProjectOut(project_id=None, name=None)

    project = session.get(Project, user.active_project_id)
    if not project:
        return ActiveProjectOut(project_id=None, name=None)

    return ActiveProjectOut(project_id=project.id, name=project.name)


def set_active_project(session: Session, user_id: int, project_id: int) -> tuple[bool, str | None]:
    upsert_user(session, user_id)
    project = session.get(Project, project_id)
    if not project:
        return False, f"Project {project_id} not found"
    if project.status != "active":
        return False, f"Project '{project.name}' is not active"

    user = session.get(User, user_id)
    assert user is not None
    user.active_project_id = project_id
    session.flush()
    return True, None
