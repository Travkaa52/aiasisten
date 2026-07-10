"""
handlers/access.py
Общие функции доступа: получить-или-создать пользователя в БД,
проверить owner/whitelist/blacklist, обновить last_seen/message_count.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from assistant.config import config
from assistant.database import get_session
from assistant.models import User


async def get_or_create_user(telegram_id: int, username: str | None, display_name: str | None) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        now = dt.datetime.now(dt.timezone.utc)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                display_name=display_name,
                is_owner=telegram_id in config.owner_ids,
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
        await session.flush()
        await session.refresh(user)
        return user


def is_owner(telegram_id: int) -> bool:
    return telegram_id in config.owner_ids
