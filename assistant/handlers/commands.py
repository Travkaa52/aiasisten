"""
handlers/commands.py
Все текстовые self-команды владельца аккаунта (Telethon userbot-стиль:
команды отправляются из своего же аккаунта, outgoing=True).

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

from sqlalchemy import select
from telethon import TelegramClient, events

from assistant.ai import AIError, ai_client
from assistant.database import get_session
from assistant.handlers import dnd as dnd_module
from assistant.handlers import notes as notes_module
from assistant.handlers import reminders as reminders_module
from assistant.handlers import search as search_module
from assistant.logger import log
from assistant.memory import memory
from assistant.models import StatEntry, User
from assistant.utils.text_utils import chunk_text, is_command, strip_command
from assistant.utils.validators import TimeParseError

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


async def _reply_target_text(event: events.NewMessage.Event) -> str | None:
    if not event.message.is_reply:
        return None
    reply = await event.message.get_reply_message()
    return reply.raw_text if reply and reply.raw_text else None


def register_command_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/help"))
    async def _help(event: events.NewMessage.Event) -> None:
        await event.reply(HELP_TEXT)

    # ------------------------------------------------------------------
    # AI-текстовые функции
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/rewrite"))
    async def _rewrite(event: events.NewMessage.Event) -> None:
        style = strip_command(event.raw_text) or "более вежливо и профессионально"
        text = await _reply_target_text(event)
        if not text:
            await event.reply("⚠️ Ответьте командой /rewrite на сообщение, которое нужно переписать.")
            return
        status = await event.reply("✍️ Переписываю...")
        try:
            result = await ai_client.rewrite(text, style)
            chunks = chunk_text(result)
            await status.edit(chunks[0])
            for chunk in chunks[1:]:
                await event.reply(chunk)
        except AIError as exc:
            await status.edit(f"❌ {exc}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/translate"))
    async def _translate(event: events.NewMessage.Event) -> None:
        target_lang = strip_command(event.raw_text) or "английский"
        text = await _reply_target_text(event)
        if not text:
            await event.reply("⚠️ Ответьте командой /translate <язык> на сообщение для перевода.")
            return
        status = await event.reply("🌐 Перевожу...")
        try:
            result = await ai_client.translate(text, target_lang)
            await status.edit(result[:4096])
        except AIError as exc:
            await status.edit(f"❌ {exc}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/summarize"))
    async def _summarize(event: events.NewMessage.Event) -> None:
        text = await _reply_target_text(event)
        if not text:
            await event.reply("⚠️ Ответьте командой /summarize на сообщение для саммари.")
            return
        status = await event.reply("📋 Делаю саммари...")
        try:
            result = await ai_client.summarize(text)
            await status.edit(result[:4096])
        except AIError as exc:
            await status.edit(f"❌ {exc}")

    # ------------------------------------------------------------------
    # Заметки
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/note"))
    async def _note(event: events.NewMessage.Event) -> None:
        args = strip_command(event.raw_text)
        owner_id = event.chat_id
        sub, _, rest = args.partition(" ")
        sub = sub.lower()

        if sub == "add":
            title, _, content = rest.partition("|")
            if not content:
                await event.reply("⚠️ Формат: /note add Заголовок | Текст заметки")
                return
            note = await notes_module.add_note(owner_id, title, content)
            await event.reply(f"✅ Заметка сохранена: {notes_module.format_note_line(note)}")

        elif sub == "list":
            items = await notes_module.list_notes(owner_id)
            if not items:
                await event.reply("📭 Заметок пока нет.")
                return
            lines = "\n".join(notes_module.format_note_line(n) for n in items)
            await event.reply(f"📚 Ваши заметки:\n{lines}")

        elif sub == "get":
            try:
                note_id = int(rest.strip())
            except ValueError:
                await event.reply("⚠️ Формат: /note get <id>")
                return
            note = await notes_module.get_note(owner_id, note_id)
            if note is None:
                await event.reply("❌ Заметка не найдена.")
                return
            await event.reply(f"📝 {note.title}\n\n{note.content}")

        elif sub == "del":
            try:
                note_id = int(rest.strip())
            except ValueError:
                await event.reply("⚠️ Формат: /note del <id>")
                return
            deleted = await notes_module.delete_note(owner_id, note_id)
            await event.reply("🗑️ Заметка удалена." if deleted else "❌ Заметка не найдена.")

        else:
            await event.reply("⚠️ Использование: /note add|list|get|del ...")

    # ------------------------------------------------------------------
    # Напоминания
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/remind\b"))
    async def _remind(event: events.NewMessage.Event) -> None:
        args = strip_command(event.raw_text)
        raw_time, _, text = args.partition(" ")
        if not raw_time or not text:
            await event.reply("⚠️ Формат: /remind <время> <текст>. Пример: /remind 30m Позвонить врачу")
            return
        try:
            reminder = await reminders_module.create_reminder(
                event.chat_id, event.chat_id, raw_time, text
            )
        except TimeParseError as exc:
            await event.reply(f"⚠️ {exc}")
            return
        await event.reply(
            f"⏰ Напоминание #{reminder.id} установлено на "
            f"{reminder.remind_at:%Y-%m-%d %H:%M UTC}."
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/reminders"))
    async def _reminders_list(event: events.NewMessage.Event) -> None:
        items = await reminders_module.list_active_reminders(event.chat_id)
        if not items:
            await event.reply("📭 Активных напоминаний нет.")
            return
        lines = "\n".join(
            f"#{r.id} — {r.text} ({r.remind_at:%Y-%m-%d %H:%M UTC})" for r in items
        )
        await event.reply(f"⏰ Активные напоминания:\n{lines}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/unremind"))
    async def _unremind(event: events.NewMessage.Event) -> None:
        try:
            reminder_id = int(strip_command(event.raw_text))
        except ValueError:
            await event.reply("⚠️ Формат: /unremind <id>")
            return
        ok = await reminders_module.cancel_reminder(event.chat_id, reminder_id)
        await event.reply("✅ Напоминание отменено." if ok else "❌ Напоминание не найдено.")

    # ------------------------------------------------------------------
    # Поиск
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/search"))
    async def _search(event: events.NewMessage.Event) -> None:
        query = strip_command(event.raw_text)
        if not query:
            await event.reply("⚠️ Формат: /search <запрос>")
            return
        results = await search_module.search_messages(event.chat_id, query)
        if not results:
            await event.reply("🔍 Ничего не найдено.")
            return
        lines = "\n".join(
            f"[{m.timestamp:%Y-%m-%d %H:%M}] {m.text[:120]}" for m in results
        )
        await event.reply(f"🔍 Найдено:\n{lines}")

    # ------------------------------------------------------------------
    # Whitelist / Blacklist
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/whitelist"))
    async def _whitelist(event: events.NewMessage.Event) -> None:
        await _manage_list(event, field="is_whitelisted", label="белый список")

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/blacklist"))
    async def _blacklist(event: events.NewMessage.Event) -> None:
        await _manage_list(event, field="is_blacklisted", label="чёрный список")

    async def _manage_list(event: events.NewMessage.Event, field: str, label: str) -> None:
        args = strip_command(event.raw_text)
        sub, _, rest = args.partition(" ")
        sub = sub.lower()

        if sub == "list":
            async with get_session() as session:
                result = await session.execute(select(User).where(getattr(User, field).is_(True)))
                users = list(result.scalars().all())
            if not users:
                await event.reply(f"📭 {label.capitalize()} пуст.")
                return
            lines = "\n".join(f"{u.telegram_id} — @{u.username or 'без username'}" for u in users)
            await event.reply(f"📋 {label.capitalize()}:\n{lines}")
            return

        if sub not in {"add", "remove"}:
            await event.reply(f"⚠️ Использование: /{label.split()[0]} add|remove|list <id>")
            return

        try:
            target_id = int(rest.strip())
        except ValueError:
            await event.reply("⚠️ Укажите числовой Telegram ID.")
            return

        async with get_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == target_id))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(telegram_id=target_id)
                session.add(user)
            setattr(user, field, sub == "add")

        action = "добавлен в" if sub == "add" else "удалён из"
        await event.reply(f"✅ Пользователь {target_id} {action} {label}.")

    # ------------------------------------------------------------------
    # DND
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/dnd"))
    async def _dnd(event: events.NewMessage.Event) -> None:
        arg = strip_command(event.raw_text).lower()
        if arg == "on":
            await dnd_module.set_dnd(True)
            await event.reply("🌙 Режим «не беспокоить» включён.")
        elif arg == "off":
            await dnd_module.set_dnd(False)
            await event.reply("🔔 Режим «не беспокоить» выключен.")
        else:
            status = await dnd_module.is_dnd_enabled()
            await event.reply(f"ℹ️ DND сейчас: {'включён 🌙' if status else 'выключен 🔔'}")

    # ------------------------------------------------------------------
    # Память
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/memory"))
    async def _memory(event: events.NewMessage.Event) -> None:
        arg = strip_command(event.raw_text).lower()
        if arg == "clear":
            await memory.clear(event.chat_id)
            await event.reply("🧹 Контекст памяти этого чата очищен.")
        else:
            await event.reply("⚠️ Использование: /memory clear")

    # ------------------------------------------------------------------
    # Статистика
    # ------------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/stats"))
    async def _stats(event: events.NewMessage.Event) -> None:
        today = dt.date.today()
        async with get_session() as session:
            result = await session.execute(select(StatEntry).where(StatEntry.date == today))
            entry = result.scalar_one_or_none()
            users_result = await session.execute(select(User))
            total_users = len(list(users_result.scalars().all()))

        if entry is None:
            await event.reply(
                f"📊 Статистика за {today}:\nСообщений: 0\nAI-вызовов: 0\n"
                f"Спам заблокирован: 0\nОшибок: 0\nВсего пользователей в БД: {total_users}"
            )
            return

        await event.reply(
            f"📊 Статистика за {today}:\n"
            f"Сообщений обработано: {entry.messages_processed}\n"
            f"AI-вызовов: {entry.ai_calls}\n"
            f"Спам заблокирован: {entry.spam_blocked}\n"
            f"Ошибок: {entry.errors}\n"
            f"Всего пользователей в БД: {total_users}"
        )

    log.info("Текстовые команды зарегистрированы.")
