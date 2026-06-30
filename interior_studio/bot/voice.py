"""Голосовые сообщения: Telegram voice.ogg → OpenAI Whisper → текст."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from openai import OpenAI
from telegram import File

from interior_studio.config import OPENAI_API_KEY, WHISPER_MODEL

logger = logging.getLogger(__name__)

WHISPER_ERROR_MESSAGE = "Не разобрал голосовое, напиши текстом."


def create_whisper_client(api_key: str | None = None) -> OpenAI:
    key = api_key or OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY is required for Whisper")
    return OpenAI(api_key=key)


async def download_voice_file(tg_file: File, destination: Path) -> None:
    await tg_file.download_to_drive(custom_path=str(destination))


def transcribe_audio_file(client: OpenAI, audio_path: Path, model: str | None = None) -> str:
    """Синхронный вызов Whisper API."""
    with audio_path.open("rb") as audio:
        response = client.audio.transcriptions.create(
            model=model or WHISPER_MODEL,
            file=audio,
            language="ru",
        )
    return (response.text or "").strip()


async def transcribe_telegram_voice(
    tg_file: File,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> str:
    """Скачивает voice.ogg и возвращает транскрипт или пустую строку при ошибке."""
    whisper_client = client or create_whisper_client()
    suffix = Path(tg_file.file_path or "voice.ogg").suffix or ".ogg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await download_voice_file(tg_file, tmp_path)
        return transcribe_audio_file(whisper_client, tmp_path, model=model)
    except Exception:
        logger.exception("Whisper transcription failed")
        return ""
    finally:
        tmp_path.unlink(missing_ok=True)
