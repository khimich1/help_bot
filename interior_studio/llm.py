"""Фабрика Chat LLM: OpenAI или DeepSeek (OpenAI-compatible API)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from interior_studio.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_PROVIDER,
    OPENAI_MODEL,
)


def create_chat_llm() -> ChatOpenAI:
    """Создаёт ChatOpenAI для ReAct-агента по LLM_PROVIDER из .env."""
    if LLM_PROVIDER == "deepseek":
        if not DEEPSEEK_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=deepseek, но DEEPSEEK_API_KEY не задан в .env"
            )
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            temperature=0,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    # openai — ключ берётся из OPENAI_API_KEY (env или .env)
    return ChatOpenAI(model=OPENAI_MODEL, temperature=0)
