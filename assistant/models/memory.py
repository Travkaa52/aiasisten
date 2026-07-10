from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.models.base import Base


class MemoryEntry(Base):
    """Скользящее окно контекста диалога по каждому чату для AI-ответов."""

    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), index=True
    )
