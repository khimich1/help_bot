"""Tool search_web для ReAct-агента."""

from __future__ import annotations

from pydantic import BaseModel, Field

from interior_studio.web.search import search_web


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
        "тему (инфраструктура ЖК, цены, нормы). Не для фактов из брифа/анкеты."
    ),
    "args_schema": SearchWebArgs,
}


def search_web_impl(
    session,
    user_id: int,
    query: str,
    max_results: int | None = None,
) -> str:
    return search_web(query, max_results=max_results)
