from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from assistant.models.base import Base


class BusinessConnectionRecord(Base):
    """Связь между business_connection_id (функция Telegram Business
    «Чат-боты» / Automated messages) и Telegram ID владельца аккаунта,
    подключившего бота. Используется, чтобы:
      - отличать сообщения владельца (self-команды) от сообщений клиентов
        (автоответчик) внутри одного business-чата;
      - подставлять business_connection_id при отправке сообщений
        (bot.send_message(..., business_connection_id=...)), чтобы ответ
        выглядел отправленным от лица подключённого аккаунта, а не от бота.
    """

    __tablename__ = "business_connections"

    connection_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), onupdate=lambda: dt.datetime.now(dt.timezone.utc)
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BusinessConnectionRecord id={self.connection_id} owner={self.owner_user_id}>"
