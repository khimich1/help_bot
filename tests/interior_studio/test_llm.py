"""Тесты фабрики LLM."""

from unittest.mock import patch

import pytest

from interior_studio.llm import create_chat_llm


def test_create_chat_llm_openai():
    with patch("interior_studio.llm.LLM_PROVIDER", "openai"), patch(
        "interior_studio.llm.OPENAI_MODEL", "gpt-4o-mini"
    ), patch("interior_studio.llm.ChatOpenAI") as mock_cls:
        create_chat_llm()
        mock_cls.assert_called_once_with(model="gpt-4o-mini", temperature=0)


def test_create_chat_llm_deepseek():
    with patch("interior_studio.llm.LLM_PROVIDER", "deepseek"), patch(
        "interior_studio.llm.DEEPSEEK_API_KEY", "sk-test"
    ), patch("interior_studio.llm.DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"), patch(
        "interior_studio.llm.DEEPSEEK_MODEL", "deepseek-chat"
    ), patch("interior_studio.llm.ChatOpenAI") as mock_cls:
        create_chat_llm()
        mock_cls.assert_called_once_with(
            model="deepseek-chat",
            temperature=0,
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )


def test_create_chat_llm_deepseek_without_key_raises():
    with patch("interior_studio.llm.LLM_PROVIDER", "deepseek"), patch(
        "interior_studio.llm.DEEPSEEK_API_KEY", None
    ):
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            create_chat_llm()
