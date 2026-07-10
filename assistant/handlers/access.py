"""
handlers/access.py
Общие функции доступа: получить-или-создать пользователя в БД, проверить
owner/whitelist/blacklist, обновить last_seen/message_count, а также
определить владельца через функцию Telegram Business «Чат-боты»
(Business Connection) — вместо проверки outgoing=True из Telethon.
"""

from __future__ import annotations

import datetime as dt

from aiogram.types import Message
from sqlalchemy import select

from assistant.config import config
from assistant.database import get_session
from assistant.handlers.business import get_owner_id_for_connection
from assistant.models import User


async def get_or_create_user(
    telegram_id: int, username: str | None, display_name: str | None, is_owner: bool = False
) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        now = dt.datetime.now(dt.timezone.utc)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                display_name=display_name,
                is_owner=is_owner or telegram_id in config.owner_ids,
                message_count=1,
                first_seen=now,
                last_seen=now,
            )
            session.add(user)
        else:
            user.username = username or user.username
            user.display_name = display_name or user.display_name
            user.last_seen = now
            user.message_count += 1
            if is_owner:
                user.is_owner = True
        await session.flush()
        await session.refresh(user)
        return user


def is_owner_id(telegram_id: int) -> bool:
    """Синхронная проверка по статическому списку OWNER_IDS из конфига."""
    return telegram_id in config.owner_ids


async def is_message_from_owner(message: Message) -> bool:
    """Определяет, что сообщение отправлено владельцем аккаунта.

    Владелец определяется двумя способами:
      1. Telegram ID есть в OWNER_IDS (напр. для прямых сообщений боту).
      2. Сообщение пришло через Business Connection
         (функция Telegram Business «Чат-боты» / Automated messages),
         и отправитель совпадает с владельцем этой связки.
    """
    if message.from_user is None:
        return False
    if message.from_user.id in config.owner_ids:
        return True
    if message.business_connection_id:
        owner_id = await get_owner_id_for_connection(message.business_connection_id)
        return owner_id is not None and owner_id == message.from_user.id
    return False
