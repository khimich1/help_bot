"""Сервис проектов."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from interior_studio.db.models import Project
from interior_studio.schemas.project import ProjectOut


class ProjectAlreadyExistsError(Exception):
    pass


def list_projects(session: Session, status: str = "active") -> list[ProjectOut]:
    stmt = select(Project).where(Project.status == status).order_by(Project.name)
    projects = session.scalars(stmt).all()
    return [ProjectOut(id=p.id, name=p.name, status=p.status) for p in projects]


def create_project(session: Session, name: str) -> ProjectOut:
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty")
    project = Project(name=name, status="active")
    session.add(project)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ProjectAlreadyExistsError(f"Project '{name}' already exists") from exc
    return ProjectOut(id=project.id, name=project.name, status=project.status)


def find_matching_projects(session: Session, query: str, status: str = "active") -> list[ProjectOut]:
    """Ищет проекты по подстроке в названии (для disambiguation)."""
    q = query.strip().lower()
    if not q:
        return []
    projects = session.scalars(
        select(Project).where(Project.status == status).order_by(Project.name)
    ).all()
    matches = [p for p in projects if q in p.name.lower()]
    return [ProjectOut(id=p.id, name=p.name, status=p.status) for p in matches]


def get_project_by_id(session: Session, project_id: int) -> ProjectOut | None:
    project = session.get(Project, project_id)
    if not project:
        return None
    return ProjectOut(id=project.id, name=project.name, status=project.status)
