"""
handlers/dnd.py
Режим "Не беспокоить": если включён, автоответчик не реагирует на входящие
сообщения (кроме owner-команд). Настройка хранится в таблице settings.
"""

from __future__ import annotations

from sqlalchemy import select

from assistant.database import get_session
from assistant.models import Setting

DND_KEY = "dnd_enabled"


async def is_dnd_enabled() -> bool:
    async with get_session() as session:
        result = await session.execute(select(Setting).where(Setting.key == DND_KEY))
        setting = result.scalar_one_or_none()
        return setting is not None and setting.value == "1"


async def set_dnd(enabled: bool) -> None:
    async with get_session() as session:
        result = await session.execute(select(Setting).where(Setting.key == DND_KEY))
        setting = result.scalar_one_or_none()
        if setting is None:
            session.add(Setting(key=DND_KEY, value="1" if enabled else "0"))
        else:
            setting.value = "1" if enabled else "0"
