"""
handlers/search.py
Полнотекстовый поиск (LIKE) по логу сообщений и заметкам владельца.
"""

from __future__ import annotations

from sqlalchemy import select

from assistant.database import get_session
from assistant.models import MessageLog, Note


async def search_messages(chat_id: int, query: str, limit: int = 10) -> list[MessageLog]:
    pattern = f"%{query.strip()}%"
    async with get_session() as session:
        result = await session.execute(
            select(MessageLog)
            .where(MessageLog.chat_id == chat_id, MessageLog.text.like(pattern))
            .order_by(MessageLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def search_notes(owner_id: int, query: str, limit: int = 10) -> list[Note]:
    pattern = f"%{query.strip()}%"
    async with get_session() as session:
        result = await session.execute(
            select(Note)
            .where(
                Note.owner_id == owner_id,
                (Note.title.like(pattern) | Note.content.like(pattern)),
            )
            .order_by(Note.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
