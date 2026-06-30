"""In-memory сессии пользователей: история диалога и pending disambiguation."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage

HISTORY_LIMIT = 20
PENDING_TIMEOUT = datetime.timedelta(minutes=30)


@dataclass
class PendingDisambiguation:
    """Ожидание выбора проекта пользователем."""

    original_text: str
    candidate_project_ids: list[int]
    is_voice: bool
    created_at: datetime = field(default_factory=datetime.datetime.utcnow)


@dataclass
class UserSession:
    messages: list[BaseMessage] = field(default_factory=list)
    pending: PendingDisambiguation | None = None
    last_message_is_voice: bool = False


class SessionStore:
    """Хранилище сессий per telegram_user_id (в рамках процесса бота)."""

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}

    def get(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession()
        return self._sessions[user_id]

    def append_messages(self, user_id: int, new_messages: list[BaseMessage]) -> None:
        session = self.get(user_id)
        session.messages.extend(new_messages)
        if len(session.messages) > HISTORY_LIMIT:
            session.messages = session.messages[-HISTORY_LIMIT:]

    def set_pending(
        self,
        user_id: int,
        original_text: str,
        candidate_project_ids: list[int],
        is_voice: bool,
    ) -> None:
        session = self.get(user_id)
        session.pending = PendingDisambiguation(
            original_text=original_text,
            candidate_project_ids=candidate_project_ids,
            is_voice=is_voice,
        )

    def clear_pending(self, user_id: int) -> None:
        session = self.get(user_id)
        session.pending = None

    def get_pending(self, user_id: int) -> PendingDisambiguation | None:
        pending = self.get(user_id).pending
        if pending is None:
            return None
        age = datetime.datetime.utcnow() - pending.created_at
        if age > PENDING_TIMEOUT:
            self.clear_pending(user_id)
            return None
        return pending
