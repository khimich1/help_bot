"""Tool search_web для ReAct-агента."""

from __future__ import annotations

import json
from contextvars import ContextVar

from pydantic import BaseModel, Field

from interior_studio.web.search import search_web

_WEB_SEARCH_CALLED_ATTR = "_web_search_called"
_web_search_called: ContextVar[bool] = ContextVar("web_search_called", default=False)


def reset_web_search_guard(session=None) -> None:
    """Сбрасывает guard перед новым agent.invoke (один web-call на запрос)."""
    _web_search_called.set(False)
    if session is not None:
        setattr(session, _WEB_SEARCH_CALLED_ATTR, False)


def _is_web_search_called(session) -> bool:
    if session is not None and getattr(session, _WEB_SEARCH_CALLED_ATTR, False):
        return True
    return _web_search_called.get()


def _mark_web_search_called(session) -> None:
    _web_search_called.set(True)
    if session is not None:
        setattr(session, _WEB_SEARCH_CALLED_ATTR, True)


class SearchWebArgs(BaseModel):
    query: str = Field(description="Поисковый запрос (на русском или английском)")
    max_results: int | None = Field(
        default=None,
        description="Число результатов; по умолчанию из конфига WEB_SEARCH_MAX_RESULTS",
    )


SEARCH_WEB_SCHEMA = {
    "description": (
        "Поиск в интернете. Только когда пользователь явно просит «найди в интернете» / "
        "«загугли» / «поищи в сети», или после пустого search_project_knowledge на внешнюю "
        "тему (инфраструктура ЖК, цены, нормы). Не для фактов из брифа/анкеты. "
        "Не более одного вызова на вопрос пользователя."
    ),
    "args_schema": SearchWebArgs,
}


def search_web_impl(
    session,
    user_id: int,
    query: str,
    max_results: int | None = None,
) -> str:
    if _is_web_search_called(session):
        return json.dumps(
            {
                "ok": False,
                "message": "search_web already called for this request",
                "results": [],
            },
            ensure_ascii=False,
        )
    _mark_web_search_called(session)
    return search_web(query, max_results=max_results)
