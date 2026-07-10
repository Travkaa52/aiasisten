"""
handlers/antispam.py
Rate limiting входящих сообщений по chat_id. При превышении лимита
пользователь может быть автоматически добавлен в чёрный список
(если config.antispam_auto_blacklist=True).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from assistant.config import config
from assistant.database import get_session
from assistant.logger import log
from assistant.models import StatEntry, User
from assistant.utils.rate_limiter import SlidingWindowRateLimiter

_limiter = SlidingWindowRateLimiter(
    max_events=config.antispam_max_messages,
    window_seconds=config.antispam_window_seconds,
)


async def check_and_handle_spam(telegram_id: int) -> bool:
    """Возвращает True, если сообщение нужно заблокировать (это спам)."""
    is_spam = _limiter.hit(telegram_id)
    if not is_spam:
        return False

    log.warning("Обнаружен спам от пользователя {}.", telegram_id)

    async with get_session() as session:
        today = dt.date.today()
        result = await session.execute(select(StatEntry).where(StatEntry.date == today))
        entry = result.scalar_one_or_none()
        if entry is None:
            session.add(StatEntry(date=today, spam_blocked=1))
        else:
            entry.spam_blocked += 1

        if config.antispam_auto_blacklist:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user is not None and not user.is_owner:
                user.is_blacklisted = True
                log.warning("Пользователь {} автоматически добавлен в чёрный список.", telegram_id)

    return True
