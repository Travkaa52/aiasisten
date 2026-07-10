"""
handlers/reminders.py
Команды напоминаний:
  /remind <время> <текст>   например: /remind 30m Позвонить врачу
  /reminders                список активных
  /unremind <id>            отмена
Фактическая отправка происходит в scheduler.py (задача check_reminders).
"""

from __future__ import annotations

from sqlalchemy import delete, select

from assistant.database import get_session
from assistant.models import Reminder
from assistant.utils.validators import TimeParseError, parse_remind_time


async def create_reminder(owner_id: int, chat_id: int, raw_time: str, text: str) -> Reminder:
    remind_at = parse_remind_time(raw_time)  # может выбросить TimeParseError
    async with get_session() as session:
        reminder = Reminder(owner_id=owner_id, chat_id=chat_id, text=text.strip(), remind_at=remind_at)
        session.add(reminder)
        await session.flush()
        await session.refresh(reminder)
        return reminder


async def list_active_reminders(owner_id: int) -> list[Reminder]:
    async with get_session() as session:
        result = await session.execute(
            select(Reminder)
            .where(Reminder.owner_id == owner_id, Reminder.is_sent.is_(False))
            .order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())


async def cancel_reminder(owner_id: int, reminder_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            delete(Reminder).where(Reminder.owner_id == owner_id, Reminder.id == reminder_id)
        )
        return result.rowcount > 0


__all__ = ["create_reminder", "list_active_reminders", "cancel_reminder", "TimeParseError"]
