"""
scheduler.py
APScheduler (AsyncIOScheduler) для фоновых периодических задач внутри
одного запуска процесса: проверка напоминаний, агрегация статистики,
очистка устаревших данных кэша.

Так как процесс в GitHub Actions живёт ограниченное время
(config.run_duration_seconds), эти задачи выполняются часто (раз в
15-30 секунд), чтобы успеть отработать в рамках короткого окна жизни.
"""

from __future__ import annotations

import datetime as dt

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from assistant.database import get_session
from assistant.logger import log
from assistant.models import Reminder, StatEntry
from assistant.cache.cache_manager import cache


class TaskScheduler:
    def __init__(self, telegram_client) -> None:
        self.client = telegram_client
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self.scheduler.add_job(
            self._check_reminders,
            trigger=IntervalTrigger(seconds=15),
            id="check_reminders",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self._cleanup_cache,
            trigger=IntervalTrigger(seconds=60),
            id="cleanup_cache",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        log.info("Планировщик задач запущен.")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            log.info("Планировщик задач остановлен.")

    async def _check_reminders(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Reminder).where(
                        Reminder.is_sent.is_(False), Reminder.remind_at <= now
                    )
                )
                due = list(result.scalars().all())
                for reminder in due:
                    try:
                        await self.client.send_message(
                            reminder.chat_id, f"⏰ Напоминание: {reminder.text}"
                        )
                        log.info(
                            "Напоминание #{} отправлено в чат {}.",
                            reminder.id,
                            reminder.chat_id,
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.error("Не удалось отправить напоминание #{}: {}", reminder.id, exc)
                if due:
                    ids = [r.id for r in due]
                    await session.execute(
                        update(Reminder).where(Reminder.id.in_(ids)).values(is_sent=True)
                    )
        except Exception as exc:  # noqa: BLE001
            log.exception("Ошибка в задаче проверки напоминаний: {}", exc)
            await self._record_error()

    async def _cleanup_cache(self) -> None:
        try:
            removed = cache.cleanup_expired()
            if removed:
                log.debug("Очищено {} устаревших записей кэша.", removed)
        except Exception as exc:  # noqa: BLE001
            log.exception("Ошибка при очистке кэша: {}", exc)

    async def _record_error(self) -> None:
        today = dt.date.today()
        async with get_session() as session:
            result = await session.execute(select(StatEntry).where(StatEntry.date == today))
            entry = result.scalar_one_or_none()
            if entry is None:
                entry = StatEntry(date=today, errors=1)
                session.add(entry)
            else:
                entry.errors += 1
