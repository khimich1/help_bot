"""Сервис семантического поиска по документам проекта."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from interior_studio.config import CHROMA_PERSIST_DIR, KNOWLEDGE_TOP_K, OPENAI_EMBEDDING_MODEL
from interior_studio.db.models import Project
from interior_studio.knowledge.store import KnowledgeStore
from interior_studio.services import user_context


def _resolve_project(
    session: Session,
    user_id: int,
    project_id: int | None,
) -> tuple[Project | None, str | None]:
    if project_id is not None:
        project = session.get(Project, project_id)
        if not project:
            return None, f"Project {project_id} not found"
        return project, None

    active = user_context.get_active_project(session, user_id)
    if not active.project_id:
        return None, "No active project. Use set_active_project or pass project_id."
    project = session.get(Project, active.project_id)
    if not project:
        return None, "Active project not found in database."
    return project, None


def search_project_knowledge(
    session: Session,
    user_id: int,
    query: str,
    *,
    project_id: int | None = None,
    room: str | None = None,
    doc_type: str | None = None,
    store: KnowledgeStore | None = None,
) -> str:
    """Ищет фрагменты в Chroma; возвращает JSON-строку для tool."""
    query = query.strip()
    if not query:
        return json.dumps({"ok": False, "message": "Query cannot be empty"}, ensure_ascii=False)

    project, err = _resolve_project(session, user_id, project_id)
    if err or project is None:
        return json.dumps({"ok": False, "message": err}, ensure_ascii=False)

    knowledge_store = store or KnowledgeStore(
        persist_dir=CHROMA_PERSIST_DIR,
        embedding_model=OPENAI_EMBEDDING_MODEL,
    )
    results = knowledge_store.search(
        project.name,
        query,
        top_k=KNOWLEDGE_TOP_K,
        doc_type=doc_type,
        room=room,
    )

    return json.dumps(
        {
            "ok": True,
            "project_name": project.name,
            "results": results,
        },
        ensure_ascii=False,
    )
