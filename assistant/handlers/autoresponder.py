"""
handlers/autoresponder.py
Главный обработчик входящих сообщений от клиентов (не от владельца):
  1. логирует сообщение и обновляет профиль пользователя;
  2. проверяет антиспам;
  3. проверяет blacklist/whitelist;
  4. проверяет DND;
  5. запрашивает AI-ответ с учётом памяти диалога и отвечает.

Работает как с обычными личными сообщениями боту (`message`), так и с
сообщениями клиентов бизнес-аккаунта (`business_message`), полученными
через функцию Telegram Business «Чат-боты». Сообщения владельца
аккаунта (self-команды) обрабатываются отдельно в handlers/commands.py
и handlers/media.py — этот модуль их пропускает.
"""

from __future__ import annotations

import datetime as dt

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import select

from assistant.ai import AIError, ai_client
from assistant.config import config
from assistant.database import get_session
from assistant.handlers.access import get_or_create_user, is_message_from_owner
from assistant.handlers.antispam import check_and_handle_spam
from assistant.handlers.dnd import is_dnd_enabled
from assistant.logger import log
from assistant.memory import memory
from assistant.models import MessageLog, StatEntry

router = Router(name="autoresponder")

SYSTEM_PROMPT = (
    "Ты — персональный AI-ассистент пользователя в Telegram. Отвечай кратко, "
    "по делу и дружелюбно. Если вопрос требует уточнения — уточни. "
    "Отвечай на языке собеседника."
)


class IsNotOwner(BaseFilter):
    """Пропускает только сообщения не от владельца аккаунта (клиенты)."""

    async def __call__(self, message: Message) -> bool:
        return not await is_message_from_owner(message)


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


async def _handle_incoming(message: Message, bot: Bot) -> None:
    sender = message.from_user
    if sender is None or sender.is_bot:
        return

    telegram_id = sender.id
    text = message.text or message.caption or ""

    user = await get_or_create_user(telegram_id, sender.username, sender.first_name)
    await _log_message(message.chat.id, telegram_id, "in", text)
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

    await memory.add_message(message.chat.id, "user", text)
    context = await memory.get_context(message.chat.id)

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

    await bot.send_message(
        chat_id=message.chat.id,
        text=reply,
        business_connection_id=message.business_connection_id,
        reply_to_message_id=message.message_id,
    )
    await memory.add_message(message.chat.id, "assistant", reply)
    await _log_message(message.chat.id, telegram_id, "out", reply)


@router.business_message(IsNotOwner())
async def _on_business_message(message: Message, bot: Bot) -> None:
    if message.chat.type == "channel":
        return
    await _handle_incoming(message, bot)


@router.message(IsNotOwner(), F.chat.type.in_({"private", "group", "supergroup"}))
async def _on_message(message: Message, bot: Bot) -> None:
    await _handle_incoming(message, bot)


def register_autoresponder(dp) -> None:
    dp.include_router(router)
    log.info("Автоответчик зарегистрирован.")
