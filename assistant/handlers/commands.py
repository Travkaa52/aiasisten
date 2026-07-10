"""
handlers/commands.py
Все текстовые self-команды владельца аккаунта. Раньше это были
outgoing=True команды Telethon-юзербота; теперь это сообщения, отправленные
владельцем в чате, подключённом через функцию Telegram Business
«Чат-боты» (business_message), либо личные сообщения боту напрямую
(message) — в обоих случаях проверяется, что отправитель является
владельцем (см. handlers/access.py::is_message_from_owner).

Команды:
  /help
  /rewrite <стиль> | <текст-в-reply>
  /translate <язык> | <текст-в-reply>
  /summarize (в reply на длинное сообщение)
  /note add|list|get|del ...
  /remind <время> <текст>
  /reminders
  /unremind <id>
  /search <запрос>
  /stats
  /whitelist add|remove|list <user_id>
  /blacklist add|remove|list <user_id>
  /dnd on|off|status
  /memory clear
"""

from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import select

from assistant.ai import AIError, ai_client
from assistant.database import get_session
from assistant.handlers import dnd as dnd_module
from assistant.handlers import notes as notes_module
from assistant.handlers import reminders as reminders_module
from assistant.handlers import search as search_module
from assistant.handlers.access import is_message_from_owner
from assistant.logger import log
from assistant.memory import memory
from assistant.models import StatEntry, User
from assistant.utils.text_utils import chunk_text, strip_command
from assistant.utils.validators import TimeParseError

router = Router(name="commands")

HELP_TEXT = """🤖 AI Assistant — доступные команды:

/rewrite <стиль> — переписать текст (в ответ на сообщение)
/translate <язык> — перевести текст (в ответ на сообщение)
/summarize — сделать саммари (в ответ на сообщение)
/ocr — распознать текст на фото (в ответ на фото)
/voice — расшифровать голосовое (в ответ на voice)
/analyze — проанализировать файл (в ответ на документ)
/imagine <промпт> — сгенерировать изображение

/note add <заголовок> | <текст> — добавить заметку
/note list — список заметок
/note get <id> — показать заметку
/note del <id> — удалить заметку

/remind <время> <текст> — напоминание (пример: /remind 30m Позвонить)
/reminders — активные напоминания
/unremind <id> — отменить напоминание

/search <запрос> — поиск по истории сообщений

/whitelist add|remove|list <id>
/blacklist add|remove|list <id>
/dnd on|off|status — режим "не беспокоить"
/memory clear — очистить контекст текущего чата
/stats — статистика ассистента
/help — это сообщение"""


class IsOwner(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return await is_message_from_owner(message)


async def _reply_target_text(message: Message) -> str | None:
    if message.reply_to_message is None:
        return None
    reply = message.reply_to_message
    return reply.text or reply.caption


def _register(pattern: str, handler) -> None:
    """Регистрирует один и тот же owner-обработчик и для обычных сообщений
    (message), и для сообщений в чатах, подключённых через функцию
    Telegram Business «Чат-боты» (business_message)."""
    text_filter = F.text.regexp(pattern)
    router.message.register(handler, IsOwner(), text_filter)
    router.business_message.register(handler, IsOwner(), text_filter)


# ----------------------------------------------------------------------
# /help
# ----------------------------------------------------------------------
async def _help(message: Message) -> None:
    await message.reply(HELP_TEXT)


# ----------------------------------------------------------------------
# AI-текстовые функции
# ----------------------------------------------------------------------
async def _rewrite(message: Message) -> None:
    style = strip_command(message.text) or "более вежливо и профессионально"
    text = await _reply_target_text(message)
    if not text:
        await message.reply("⚠️ Ответьте командой /rewrite на сообщение, которое нужно переписать.")
        return
    status = await message.reply("✍️ Переписываю...")
    try:
        result = await ai_client.rewrite(text, style)
        chunks = chunk_text(result)
        await status.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await message.reply(chunk)
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")


async def _translate(message: Message) -> None:
    target_lang = strip_command(message.text) or "английский"
    text = await _reply_target_text(message)
    if not text:
        await message.reply("⚠️ Ответьте командой /translate <язык> на сообщение для перевода.")
        return
    status = await message.reply("🌐 Перевожу...")
    try:
        result = await ai_client.translate(text, target_lang)
        await status.edit_text(result[:4096])
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")


async def _summarize(message: Message) -> None:
    text = await _reply_target_text(message)
    if not text:
        await message.reply("⚠️ Ответьте командой /summarize на сообщение для саммари.")
        return
    status = await message.reply("📋 Делаю саммари...")
    try:
        result = await ai_client.summarize(text)
        await status.edit_text(result[:4096])
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")


# ----------------------------------------------------------------------
# Заметки
# ----------------------------------------------------------------------
async def _note(message: Message) -> None:
    args = strip_command(message.text)
    owner_id = message.chat.id
    sub, _, rest = args.partition(" ")
    sub = sub.lower()

    if sub == "add":
        title, _, content = rest.partition("|")
        if not content:
            await message.reply("⚠️ Формат: /note add Заголовок | Текст заметки")
            return
        note = await notes_module.add_note(owner_id, title, content)
        await message.reply(f"✅ Заметка сохранена: {notes_module.format_note_line(note)}")

    elif sub == "list":
        items = await notes_module.list_notes(owner_id)
        if not items:
            await message.reply("📭 Заметок пока нет.")
            return
        lines = "\n".join(notes_module.format_note_line(n) for n in items)
        await message.reply(f"📚 Ваши заметки:\n{lines}")

    elif sub == "get":
        try:
            note_id = int(rest.strip())
        except ValueError:
            await message.reply("⚠️ Формат: /note get <id>")
            return
        note = await notes_module.get_note(owner_id, note_id)
        if note is None:
            await message.reply("❌ Заметка не найдена.")
            return
        await message.reply(f"📝 {note.title}\n\n{note.content}")

    elif sub == "del":
        try:
            note_id = int(rest.strip())
        except ValueError:
            await message.reply("⚠️ Формат: /note del <id>")
            return
        deleted = await notes_module.delete_note(owner_id, note_id)
        await message.reply("🗑️ Заметка удалена." if deleted else "❌ Заметка не найдена.")

    else:
        await message.reply("⚠️ Использование: /note add|list|get|del ...")


# ----------------------------------------------------------------------
# Напоминания
# ----------------------------------------------------------------------
async def _remind(message: Message) -> None:
    args = strip_command(message.text)
    raw_time, _, text = args.partition(" ")
    if not raw_time or not text:
        await message.reply("⚠️ Формат: /remind <время> <текст>. Пример: /remind 30m Позвонить врачу")
        return
    try:
        reminder = await reminders_module.create_reminder(
            message.chat.id,
            message.chat.id,
            raw_time,
            text,
            business_connection_id=message.business_connection_id,
        )
    except TimeParseError as exc:
        await message.reply(f"⚠️ {exc}")
        return
    await message.reply(
        f"⏰ Напоминание #{reminder.id} установлено на "
        f"{reminder.remind_at:%Y-%m-%d %H:%M UTC}."
    )


async def _reminders_list(message: Message) -> None:
    items = await reminders_module.list_active_reminders(message.chat.id)
    if not items:
        await message.reply("📭 Активных напоминаний нет.")
        return
    lines = "\n".join(f"#{r.id} — {r.text} ({r.remind_at:%Y-%m-%d %H:%M UTC})" for r in items)
    await message.reply(f"⏰ Активные напоминания:\n{lines}")


async def _unremind(message: Message) -> None:
    try:
        reminder_id = int(strip_command(message.text))
    except ValueError:
        await message.reply("⚠️ Формат: /unremind <id>")
        return
    ok = await reminders_module.cancel_reminder(message.chat.id, reminder_id)
    await message.reply("✅ Напоминание отменено." if ok else "❌ Напоминание не найдено.")


# ----------------------------------------------------------------------
# Поиск
# ----------------------------------------------------------------------
async def _search(message: Message) -> None:
    query = strip_command(message.text)
    if not query:
        await message.reply("⚠️ Формат: /search <запрос>")
        return
    results = await search_module.search_messages(message.chat.id, query)
    if not results:
        await message.reply("🔍 Ничего не найдено.")
        return
    lines = "\n".join(f"[{m.timestamp:%Y-%m-%d %H:%M}] {m.text[:120]}" for m in results)
    await message.reply(f"🔍 Найдено:\n{lines}")


# ----------------------------------------------------------------------
# Whitelist / Blacklist
# ----------------------------------------------------------------------
async def _manage_list(message: Message, field: str, label: str) -> None:
    args = strip_command(message.text)
    sub, _, rest = args.partition(" ")
    sub = sub.lower()

    if sub == "list":
        async with get_session() as session:
            result = await session.execute(select(User).where(getattr(User, field).is_(True)))
            users = list(result.scalars().all())
        if not users:
            await message.reply(f"📭 {label.capitalize()} пуст.")
            return
        lines = "\n".join(f"{u.telegram_id} — @{u.username or 'без username'}" for u in users)
        await message.reply(f"📋 {label.capitalize()}:\n{lines}")
        return

    if sub not in {"add", "remove"}:
        await message.reply(f"⚠️ Использование: /{label.split()[0]} add|remove|list <id>")
        return

    try:
        target_id = int(rest.strip())
    except ValueError:
        await message.reply("⚠️ Укажите числовой Telegram ID.")
        return

    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=target_id)
            session.add(user)
        setattr(user, field, sub == "add")

    action = "добавлен в" if sub == "add" else "удалён из"
    await message.reply(f"✅ Пользователь {target_id} {action} {label}.")


async def _whitelist(message: Message) -> None:
    await _manage_list(message, field="is_whitelisted", label="белый список")


async def _blacklist(message: Message) -> None:
    await _manage_list(message, field="is_blacklisted", label="чёрный список")


# ----------------------------------------------------------------------
# DND
# ----------------------------------------------------------------------
async def _dnd(message: Message) -> None:
    arg = strip_command(message.text).lower()
    if arg == "on":
        await dnd_module.set_dnd(True)
        await message.reply("🌙 Режим «не беспокоить» включён.")
    elif arg == "off":
        await dnd_module.set_dnd(False)
        await message.reply("🔔 Режим «не беспокоить» выключен.")
    else:
        status = await dnd_module.is_dnd_enabled()
        await message.reply(f"ℹ️ DND сейчас: {'включён 🌙' if status else 'выключен 🔔'}")


# ----------------------------------------------------------------------
# Память
# ----------------------------------------------------------------------
async def _memory(message: Message) -> None:
    arg = strip_command(message.text).lower()
    if arg == "clear":
        await memory.clear(message.chat.id)
        await message.reply("🧹 Контекст памяти этого чата очищен.")
    else:
        await message.reply("⚠️ Использование: /memory clear")


# ----------------------------------------------------------------------
# Статистика
# ----------------------------------------------------------------------
async def _stats(message: Message) -> None:
    today = dt.date.today()
    async with get_session() as session:
        result = await session.execute(select(StatEntry).where(StatEntry.date == today))
        entry = result.scalar_one_or_none()
        users_result = await session.execute(select(User))
        total_users = len(list(users_result.scalars().all()))

    if entry is None:
        await message.reply(
            f"📊 Статистика за {today}:\nСообщений: 0\nAI-вызовов: 0\n"
            f"Спам заблокирован: 0\nОшибок: 0\nВсего пользователей в БД: {total_users}"
        )
        return

    await message.reply(
        f"📊 Статистика за {today}:\n"
        f"Сообщений обработано: {entry.messages_processed}\n"
        f"AI-вызовов: {entry.ai_calls}\n"
        f"Спам заблокирован: {entry.spam_blocked}\n"
        f"Ошибок: {entry.errors}\n"
        f"Всего пользователей в БД: {total_users}"
    )


_register(r"(?i)^/help", _help)
_register(r"(?i)^/rewrite", _rewrite)
_register(r"(?i)^/translate", _translate)
_register(r"(?i)^/summarize", _summarize)
_register(r"(?i)^/note", _note)
_register(r"(?i)^/remind\b", _remind)
_register(r"(?i)^/reminders", _reminders_list)
_register(r"(?i)^/unremind", _unremind)
_register(r"(?i)^/search", _search)
_register(r"(?i)^/whitelist", _whitelist)
_register(r"(?i)^/blacklist", _blacklist)
_register(r"(?i)^/dnd", _dnd)
_register(r"(?i)^/memory", _memory)
_register(r"(?i)^/stats", _stats)


def register_command_handlers(dp) -> None:
    dp.include_router(router)
    log.info("Текстовые команды зарегистрированы.")
