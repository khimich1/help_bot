"""Неоднозначный проект: гибрид C (кнопки для текста, вопрос для голоса)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from interior_studio.schemas.project import ProjectOut
from interior_studio.services import project_service, user_context

PROJECT_HINT_PATTERNS = [
    re.compile(
        r"по\s+([\wа-яёА-ЯЁ\s\-]+?)(?:\s+—|\s+-|,|\.|$|\s+заказать|\s+добавить|\s+создать|\s+сделать|\s+нужно)",
        re.IGNORECASE,
    ),
    re.compile(r"работаем по\s+(.+)", re.IGNORECASE),
    re.compile(r"проект[уе]?\s+(.+)", re.IGNORECASE),
]

CALLBACK_PREFIX = "proj:"


class DisambiguationKind(str, Enum):
    NO_HINT = "no_hint"
    RESOLVED = "resolved"
    AMBIGUOUS_TEXT = "ambiguous_text"
    AMBIGUOUS_VOICE = "ambiguous_voice"


@dataclass
class DisambiguationResult:
    kind: DisambiguationKind
    project: ProjectOut | None = None
    candidates: list[ProjectOut] | None = None


def extract_project_hint(text: str) -> str | None:
    """Извлекает подсказку названия проекта из текста пользователя."""
    text = text.strip()
    for pattern in PROJECT_HINT_PATTERNS:
        match = pattern.search(text)
        if match:
            hint = match.group(1).strip(" .,—-")
            if hint:
                return hint
    return None


def _normalize_stem(word: str) -> str:
    """Грубая нормализация русского слова для сопоставления с названием проекта."""
    w = word.lower().strip()
    for suffix in ("ами", "ями", "ого", "ему", "ими", "ых", "их", "ым", "ой", "ам", "ем", "ую", "юю", "ая", "яя", "ов", "ев", "ы", "а", "у", "е", "и", "я", "ь", "й"):
        if len(w) > 4 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _project_matches_hint(project_name: str, hint: str) -> bool:
    pn = project_name.lower()
    h = hint.lower()
    if h in pn or pn in h:
        return True
    stem = _normalize_stem(h)
    if len(stem) >= 4 and stem in pn:
        return True
    pn_stem = _normalize_stem(pn.split()[0])
    return len(stem) >= 4 and (stem in pn_stem or pn_stem in stem)


def _find_candidates_in_text(session: Session, text: str) -> list[ProjectOut]:
    hint = extract_project_hint(text)
    all_projects = project_service.list_projects(session)

    if hint:
        matches = [
            p for p in all_projects if _project_matches_hint(p.name, hint)
        ]
        if matches:
            return matches
        matches = project_service.find_matching_projects(session, hint)
        if matches:
            return matches

    text_lower = text.lower()
    return [p for p in all_projects if p.name.lower() in text_lower]


def needs_project_disambiguation(text: str) -> bool:
    """True, если сообщение похоже на действие с проектом (не общий вопрос)."""
    lowered = text.lower()
    triggers = (
        "по ",
        "работаем",
        "заказать",
        "добавить",
        "создать",
        "сделать",
        "плитк",
        "задач",
    )
    return any(t in lowered for t in triggers)


def resolve_project_disambiguation(
    session: Session,
    user_id: int,
    text: str,
    *,
    is_voice: bool = False,
    force_check: bool = False,
) -> DisambiguationResult:
    """Определяет, нужен ли выбор проекта перед вызовом агента."""
    if not force_check and not needs_project_disambiguation(text):
        return DisambiguationResult(kind=DisambiguationKind.NO_HINT)

    candidates = _find_candidates_in_text(session, text)
    if len(candidates) == 0:
        return DisambiguationResult(kind=DisambiguationKind.NO_HINT)
    if len(candidates) == 1:
        return DisambiguationResult(
            kind=DisambiguationKind.RESOLVED,
            project=candidates[0],
        )

    active = user_context.get_active_project(session, user_id)
    if active.project_id is not None:
        for candidate in candidates:
            if candidate.id == active.project_id:
                return DisambiguationResult(
                    kind=DisambiguationKind.RESOLVED,
                    project=candidate,
                )

    kind = (
        DisambiguationKind.AMBIGUOUS_VOICE
        if is_voice
        else DisambiguationKind.AMBIGUOUS_TEXT
    )
    return DisambiguationResult(kind=kind, candidates=candidates)


def build_project_keyboard(candidates: list[ProjectOut]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p.name, callback_data=f"{CALLBACK_PREFIX}{p.id}")]
        for p in candidates
    ]
    return InlineKeyboardMarkup(buttons)


def format_voice_disambiguation_question(candidates: list[ProjectOut]) -> str:
    names = ", ".join(f"«{p.name}»" for p in candidates)
    return (
        f"Нашла {len(candidates)} проекта: {names}. "
        "Какой имеешь в виду? Напиши или скажи название."
    )


def format_text_disambiguation_question(candidates: list[ProjectOut]) -> str:
    names = ", ".join(f"«{p.name}»" for p in candidates)
    return f"Нашла несколько проектов: {names}. Выбери нужный:"


def resolve_project_from_user_reply(
    session: Session,
    reply_text: str,
    candidate_ids: list[int],
) -> ProjectOut | None:
    """Сопоставляет ответ пользователя (текст/голос) с одним из кандидатов."""
    candidates = [
        project_service.get_project_by_id(session, pid)
        for pid in candidate_ids
    ]
    candidates = [c for c in candidates if c is not None]
    if not candidates:
        return None

    reply_lower = reply_text.strip().lower()
    exact = [c for c in candidates if c.name.lower() == reply_lower]
    if len(exact) == 1:
        return exact[0]

    partial = [c for c in candidates if reply_lower in c.name.lower() or c.name.lower() in reply_lower]
    if len(partial) == 1:
        return partial[0]

    return None


def parse_callback_project_id(data: str) -> int | None:
    if not data.startswith(CALLBACK_PREFIX):
        return None
    try:
        return int(data[len(CALLBACK_PREFIX) :])
    except ValueError:
        return None
