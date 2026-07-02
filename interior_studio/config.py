"""Конфигурация Interior Studio Assistant из переменных окружения."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# ReAct-агент: openai | deepseek (OpenAI-compatible API)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/studio.db")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")

# Project knowledge (RAG)
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL",
    "paraphrase-multilingual-MiniLM-L12-v2",
)
KNOWLEDGE_TOP_K = int(os.getenv("KNOWLEDGE_TOP_K", "5"))

# Web search (DuckDuckGo MVP)
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").strip().lower()
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "ru-ru").strip()


def _parse_allowed_user_ids() -> list[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "111111111,222222222")
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


ALLOWED_USER_IDS: list[int] = _parse_allowed_user_ids()

# Первый id в .env — Сеня, второй — Рита (спека §7.2).
DESIGNER_NAMES: dict[int, str] = {}
if len(ALLOWED_USER_IDS) >= 1:
    DESIGNER_NAMES[ALLOWED_USER_IDS[0]] = "Сеня"
if len(ALLOWED_USER_IDS) >= 2:
    DESIGNER_NAMES[ALLOWED_USER_IDS[1]] = "Рита"

USER_ALIASES: dict[str, int] = {}
if len(ALLOWED_USER_IDS) >= 1:
    senya_id = ALLOWED_USER_IDS[0]
    for alias in ("сеня", "сенечка", "арсений"):
        USER_ALIASES[alias] = senya_id
if len(ALLOWED_USER_IDS) >= 2:
    rita_id = ALLOWED_USER_IDS[1]
    for alias in ("рита", "маргарита"):
        USER_ALIASES[alias] = rita_id


def resolve_assignee_id(name_or_alias: str | None) -> int | None:
    """Сопоставляет имя/алиас дизайнера с telegram_user_id."""
    if not name_or_alias:
        return None
    key = name_or_alias.strip().lower()
    if key in USER_ALIASES:
        return USER_ALIASES[key]
    for user_id, display in DESIGNER_NAMES.items():
        if display.lower() == key:
            return user_id
    return None


@lru_cache(maxsize=1)
def get_default_cli_user_id() -> int:
    """User id по умолчанию для CLI (первый дизайнер — Сеня)."""
    if not ALLOWED_USER_IDS:
        return 111111111
    return ALLOWED_USER_IDS[0]
