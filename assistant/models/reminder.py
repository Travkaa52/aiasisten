from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.models.base import Base


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    # business_connection_id чата, в котором создано напоминание (функция
    # Telegram Business «Чат-боты»). Нужен, чтобы отправить напоминание от
    # лица подключённого аккаунта, а не от бота. Может быть NULL, если
    # напоминание создано в обычном чате с ботом напрямую.
    business_connection_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    remind_at: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
