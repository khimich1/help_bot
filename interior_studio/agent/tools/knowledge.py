"""Tool search_project_knowledge для ReAct-агента."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interior_studio.knowledge.search import search_project_knowledge

DOC_TYPES = ("brief", "questionnaire", "site_report")


class SearchProjectKnowledgeArgs(BaseModel):
    query: str = Field(description="Поисковый запрос по документам проекта")
    project_id: int | None = Field(
        default=None,
        description="ID проекта; если не указан — активный проект пользователя",
    )
    room: str | None = Field(
        default=None,
        description="Фильтр по комнате, например «Мастер-ванная»",
    )
    doc_type: str | None = Field(
        default=None,
        description="Тип документа: brief, questionnaire или site_report",
    )


SEARCH_PROJECT_KNOWLEDGE_SCHEMA = {
    "description": (
        "Семантический поиск по документам проекта (бриф, анкета, отчёты выездов). "
        "Используй для вопросов о согласованных решениях, материалах, пожеланиях клиента."
    ),
    "args_schema": SearchProjectKnowledgeArgs,
}


def search_project_knowledge_impl(
    session: Session,
    user_id: int,
    query: str,
    project_id: int | None = None,
    room: str | None = None,
    doc_type: str | None = None,
) -> str:
    return search_project_knowledge(
        session,
        user_id,
        query,
        project_id=project_id,
        room=room,
        doc_type=doc_type,
    )
