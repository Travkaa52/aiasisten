"""
handlers/business.py
Отслеживание функции Telegram Business «Чат-боты» (Automated messages).

Когда владелец аккаунта подключает бота в Telegram: Настройки → Telegram
Business → Чат-боты — Telegram присылает update `business_connection` с
`connection_id` и данными владельца. Дальше все сообщения в чатах этого
бизнес-аккаунта приходят боту как `business_message` (а не `message`),
с тем же `business_connection_id`.

Этот модуль хранит связь connection_id -> owner_user_id, чтобы:
  - отличать сообщения владельца (self-команды: /rewrite, /remind и т.д.)
    от сообщений клиентов (которым нужно отвечать автоответчиком);
  - подставлять business_connection_id при отправке ответов, чтобы они
    выглядели отправленными от лица подключённого аккаунта.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import BusinessConnection
from sqlalchemy import select

from assistant.database import get_session
from assistant.logger import log
from assistant.models import BusinessConnectionRecord

router = Router(name="business")


async def save_connection(conn: BusinessConnection) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(BusinessConnectionRecord).where(
                BusinessConnectionRecord.connection_id == conn.id
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = BusinessConnectionRecord(
                connection_id=conn.id,
                owner_user_id=conn.user.id,
            )
            session.add(record)
        record.owner_user_id = conn.user.id
        record.is_enabled = conn.is_enabled
        record.can_reply = getattr(conn, "can_reply", True)

    log.info(
        "Business Connection {} обновлена: владелец={} (id={}), "
        "включено={}, разрешён ответ={}.",
        conn.id,
        conn.user.username or conn.user.first_name,
        conn.user.id,
        conn.is_enabled,
        getattr(conn, "can_reply", True),
    )


async def get_owner_id_for_connection(connection_id: str) -> int | None:
    async with get_session() as session:
        result = await session.execute(
            select(BusinessConnectionRecord.owner_user_id).where(
                BusinessConnectionRecord.connection_id == connection_id,
                BusinessConnectionRecord.is_enabled.is_(True),
            )
        )
        row = result.first()
        return row[0] if row else None


async def get_active_connection_id(owner_user_id: int) -> str | None:
    """Возвращает последний активный business_connection_id для владельца.
    Используется планировщиком (scheduler.py), чтобы отправить напоминание,
    у которого не сохранён свой business_connection_id (например, созданное
    в обычном чате с ботом)."""
    async with get_session() as session:
        result = await session.execute(
            select(BusinessConnectionRecord.connection_id)
            .where(
                BusinessConnectionRecord.owner_user_id == owner_user_id,
                BusinessConnectionRecord.is_enabled.is_(True),
            )
            .order_by(BusinessConnectionRecord.updated_at.desc())
        )
        row = result.first()
        return row[0] if row else None


@router.business_connection()
async def _on_business_connection(conn: BusinessConnection) -> None:
    await save_connection(conn)


def register_business_handlers(dp) -> None:
    dp.include_router(router)
    log.info("Обработчик Business Connection (функция «Чат-боты») зарегистрирован.")
