"""
handlers/autoresponder.py
Главный обработчик входящих (не от владельца) сообщений:
  1. логирует сообщение и обновляет профиль пользователя;
  2. проверяет антиспам;
  3. проверяет blacklist/whitelist;
  4. проверяет DND;
  5. запрашивает AI-ответ с учётом памяти диалога и отвечает.

Исходящие сообщения владельца (self-commands) обрабатываются отдельно
в handlers/commands.py и handlers/media.py — этот модуль их не трогает.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from telethon import TelegramClient, events

from assistant.ai import AIError, ai_client
from assistant.config import config
from assistant.database import get_session
from assistant.handlers.access import get_or_create_user
from assistant.handlers.antispam import check_and_handle_spam
from assistant.handlers.dnd import is_dnd_enabled
from assistant.logger import log
from assistant.memory import memory
from assistant.models import MessageLog, StatEntry

SYSTEM_PROMPT = (
    "Ты — персональный AI-ассистент пользователя в Telegram. Отвечай кратко, "
    "по делу и дружелюбно. Если вопрос требует уточнения — уточни. "
    "Отвечай на языке собеседника."
)


async def _log_message(chat_id: int, user_id: int, direction: str, text: str) -> None:
    async with get_session() as session:
        session.add(MessageLog(chat_id=chat_id, user_id=user_id, direction=direction, text=text))


async def _bump_stat(field: str) -> None:
    today = dt.date.today()
    async with get_session() as session:
        result = await session.execute(select(StatEntry).where(StatEntry.date == today))
        entry = result.scalar_one_or_none()
        if entry is None:
            entry = StatEntry(date=today)
            session.add(entry)
            await session.flush()
        setattr(entry, field, getattr(entry, field) + 1)


def register_autoresponder(client: TelegramClient) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event: events.NewMessage.Event) -> None:
        if event.is_channel and not event.is_private:
            return  # игнорируем каналы, работаем с личными чатами и группами

        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        telegram_id = sender.id
        text = event.raw_text or ""

        user = await get_or_create_user(
            telegram_id, getattr(sender, "username", None), getattr(sender, "first_name", None)
        )
        await _log_message(event.chat_id, telegram_id, "in", text)
        await _bump_stat("messages_processed")

        if user.is_blacklisted:
            log.debug("Игнорирую сообщение от заблокированного пользователя {}.", telegram_id)
            return

        if await check_and_handle_spam(telegram_id):
            await _bump_stat("spam_blocked")
            return

        if config.whitelist_mode and not user.is_whitelisted and not user.is_owner:
            log.debug("Whitelist-режим: игнорирую сообщение от {}.", telegram_id)
            return

        if await is_dnd_enabled() and not user.is_owner:
            log.debug("DND включён: не отвечаю пользователю {}.", telegram_id)
            return

        if not text.strip():
            return  # медиа без текста обрабатывается отдельно через self-команды владельца

        await memory.add_message(event.chat_id, "user", text)
        context = await memory.get_context(event.chat_id)

        try:
            reply = await ai_client.chat(context, system=SYSTEM_PROMPT)
            await _bump_stat("ai_calls")
        except AIError as exc:
            log.error("Ошибка AI при автоответе: {}", exc)
            await _bump_stat("errors")
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("Непредвиденная ошибка автоответчика: {}", exc)
            await _bump_stat("errors")
            return

        if not reply:
            return

        await event.reply(reply)
        await memory.add_message(event.chat_id, "assistant", reply)
        await _log_message(event.chat_id, telegram_id, "out", reply)

    log.info("Автоответчик зарегистрирован.")
