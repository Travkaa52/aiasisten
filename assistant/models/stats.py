from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from assistant.models.base import Base


class StatEntry(Base):
    """Агрегированная статистика по дням: сколько сообщений/AI-вызовов/ошибок."""

    __tablename__ = "stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, unique=True, index=True)
    messages_processed: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    spam_blocked: Mapped[int] = mapped_column(Integer, default=0)
