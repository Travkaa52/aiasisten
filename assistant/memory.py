"""
memory.py
Хранение и извлечение контекста диалога по каждому чату. Контекст
используется при вызовах AI, чтобы ассистент "помнил" последние сообщения.
Реализовано скользящее окно: старые записи периодически подрезаются,
чтобы БД и промпты не росли бесконечно.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from assistant.config import config
from assistant.database import get_session
from assistant.logger import log
from assistant.models import MemoryEntry


class ConversationMemory:
    """Фасад над таблицей memory_entries."""

    def __init__(self, max_context_messages: int | None = None) -> None:
        self.max_context_messages = max_context_messages or config.memory_context_messages

    async def add_message(self, chat_id: int, role: str, content: str) -> None:
        if not content:
            return
        async with get_session() as session:
            session.add(MemoryEntry(chat_id=chat_id, role=role, content=content))
        await self._trim(chat_id)

    async def get_context(self, chat_id: int) -> list[dict[str, str]]:
        """Возвращает последние N сообщений в хронологическом порядке,
        готовые для передачи в AI как messages=[...]."""
        async with get_session() as session:
            result = await session.execute(
                select(MemoryEntry)
                .where(MemoryEntry.chat_id == chat_id)
                .order_by(MemoryEntry.timestamp.desc())
                .limit(self.max_context_messages)
            )
            entries = list(result.scalars().all())
        entries.reverse()
        return [{"role": e.role, "content": e.content} for e in entries]

    async def clear(self, chat_id: int) -> None:
        async with get_session() as session:
            await session.execute(delete(MemoryEntry).where(MemoryEntry.chat_id == chat_id))
        log.info("Память чата {} очищена.", chat_id)

    async def _trim(self, chat_id: int) -> None:
        """Оставляет только последние max_context_messages * 2 записей
        (небольшой запас, чтобы не подрезать на каждой вставке)."""
        keep = self.max_context_messages * 2
        async with get_session() as session:
            result = await session.execute(
                select(MemoryEntry.id)
                .where(MemoryEntry.chat_id == chat_id)
                .order_by(MemoryEntry.timestamp.desc())
                .offset(keep)
            )
            stale_ids = [row[0] for row in result.all()]
            if stale_ids:
                await session.execute(delete(MemoryEntry).where(MemoryEntry.id.in_(stale_ids)))


memory = ConversationMemory()
