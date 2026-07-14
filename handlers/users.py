import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import StateFilter

from database.database import (
    find_autoreply, get_ai_settings, is_contact_blocked,
    log_message, add_user, get_ai_settings
)
from utils.ai import generate_ai_reply

logger = logging.getLogger(__name__)
router = Router()


@router.business_message(StateFilter(None))
async def handle_business_message(message: Message):
    """
    Главный обработчик Business-сообщений:
    1. Проверка блокировки контакта
    2. Статический автоответ из БД
    3. ИИ-ответ (Gemini) с историей диалога
    """
    trigger_text = message.text or message.caption
    if not trigger_text:
        return

    sender_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id
    sender_name = ""
    if message.from_user:
        sender_name = message.from_user.full_name or message.from_user.username or ""
        # Регистрируем пользователя
        await add_user(
            sender_id,
            message.from_user.username or "",
            message.from_user.full_name or ""
        )

    # Логируем входящее
    await log_message(sender_id, trigger_text, "incoming", chat_id)

    # Проверяем не заблокирован ли контакт
    if sender_id and await is_contact_blocked(sender_id):
        logger.info(f"Contact {sender_id} is blocked — skipping reply.")
        return

    settings = await get_ai_settings()
    if not settings.get("auto_reply_enabled", 1):
        logger.info("Auto-reply disabled in settings — skipping.")
        return

    reply_kwargs = {
        "business_connection_id": message.business_connection_id,
        "parse_mode": "HTML",
    }

    # ── ЭТАП 1: Статический автоответ из БД ─────────────────────────────────
    autoreply = await find_autoreply(trigger_text.strip())

    if autoreply:
        rtype = autoreply["reply_type"]
        reply_text = autoreply.get("reply_text", "")
        caption_text = autoreply.get("caption") or reply_text
        try:
            if rtype == "text":
                await message.answer(reply_text, **reply_kwargs)
            elif rtype == "photo":
                await message.answer_photo(autoreply["file_id"], caption=caption_text, **reply_kwargs)
            elif rtype == "video":
                await message.answer_video(autoreply["file_id"], caption=caption_text, **reply_kwargs)
            elif rtype == "document":
                await message.answer_document(autoreply["file_id"], caption=caption_text, **reply_kwargs)
            await log_message(sender_id, reply_text, "outgoing", chat_id)
            logger.info(f"Статический автоответ → чат {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки статического автоответа: {e}")
        return

    # ── ЭТАП 2: ИИ-ответ Gemini с историей ──────────────────────────────────
    mode = settings.get("mode", "smart")
    if mode == "off":
        logger.info("AI mode is OFF — skipping.")
        return

    logger.info(f"Генерация ИИ-ответа для чата {chat_id} (режим: {mode})")
    ai_text = await generate_ai_reply(
        user_text=trigger_text.strip(),
        chat_id=chat_id,
        user_name=sender_name,
    )

    if ai_text:
        try:
            await message.answer(ai_text, **reply_kwargs)
            await log_message(sender_id, ai_text, "outgoing", chat_id)
            logger.info(f"ИИ-ответ отправлен → чат {chat_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить ИИ-ответ: {e}")
