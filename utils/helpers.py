import logging
import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
import re

logger = logging.getLogger(__name__)


def format_stats(users: int, messages: int, managers: int) -> str:
    return (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"💬 Сообщений обработано: <b>{messages}</b>\n"
        f"👔 Менеджеров: <b>{managers}</b>"
    )


def format_analytics(daily: list, top: list) -> str:
    text = "📈 <b>Аналитика</b>\n\n📅 <b>Активность за 7 дней:</b>\n"
    for row in daily:
        text += f"  {row['day']}: {row['count']} сообщений\n"
    text += "\n🏆 <b>Топ-10 активных пользователей:</b>\n"
    for i, u in enumerate(top, 1):
        name = u['full_name'] or u['username'] or str(u['telegram_id'])
        text += f"  {i}. {name} — {u['msg_count']} сообщ.\n"
    return text


async def broadcast_message(
    bot: Bot,
    user_ids: list[int],
    text: str,
    photo: str = None,
    markup: InlineKeyboardMarkup = None
) -> dict:
    success = 0
    failed = 0
    for uid in user_ids:
        try:
            if photo:
                await bot.send_photo(uid, photo, caption=text, reply_markup=markup, parse_mode="HTML")
            else:
                await bot.send_message(uid, text, reply_markup=markup, parse_mode="HTML")
            success += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {uid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)
    return {"success": success, "failed": failed}


def parse_buttons_from_text(text: str):
    """Парсит кнопки из формата [Текст](https://url) в конце сообщения."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    buttons = re.findall(pattern, text)
    clean_text = re.sub(pattern, '', text).strip()
    if not buttons:
        return text, None
    builder = InlineKeyboardBuilder()
    for btn_text, url in buttons:
        builder.button(text=btn_text, url=url)
    builder.adjust(1)
    return clean_text, builder.as_markup()
