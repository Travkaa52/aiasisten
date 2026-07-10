from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.models.base import Base


class MessageLog(Base):
    """Полный лог входящих/исходящих сообщений — используется для поиска и статистики."""

    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    direction: Mapped[str] = mapped_column(String(16))  # "in" | "out"
    text: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), index=True
    )
