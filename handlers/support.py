import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_ID, SUPPORT_GROUP_ID
from database.database import (
    create_ticket, get_open_ticket, close_ticket,
    is_manager, update_manager_activity,
)
from keyboards.inline import close_ticket_btn
from keyboards.reply import cancel_menu, main_menu

logger = logging.getLogger(__name__)
router = Router()


class SupportStates(StatesGroup):
    waiting_message = State()


@router.callback_query(F.data == "support:start")
async def support_start(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    existing = await get_open_ticket(user.id)
    if existing:
        await callback.message.answer(
            "📨 У вас уже есть открытый тикет.\n"
            "Просто напишите ваш вопрос — мы ответим."
        )
        await callback.answer()
        return

    await state.set_state(SupportStates.waiting_message)
    await callback.message.answer(
        "✍️ Напишите ваш вопрос или опишите проблему.\n"
        "Нажмите ❌ Отмена для выхода.",
        reply_markup=cancel_menu()
    )
    await callback.answer()


@router.message(SupportStates.waiting_message, F.text == "❌ Отмена")
async def support_cancel(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == OWNER_ID or await is_manager(message.from_user.id)
    await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=is_admin))


@router.message(SupportStates.waiting_message)
async def support_send_message(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    ticket_id = await create_ticket(user.id)
    await state.clear()

    is_admin = user.id == OWNER_ID or await is_manager(user.id)

    if not SUPPORT_GROUP_ID:
        # Группа поддержки не настроена — просто фиксируем тикет локально
        await message.answer(
            f"✅ Ваш запрос #{ticket_id} принят!\n\n"
            "⚠️ Группа поддержки ещё не настроена владельцем бота — "
            "используйте /admin для просмотра тикетов вручную.",
            reply_markup=main_menu(is_admin=is_admin)
        )
        return

    username_display = f"@{user.username}" if user.username else f"ID: {user.id}"
    support_text = (
        f"📨 <b>Новый тикет #{ticket_id}</b>\n\n"
        f"👤 Пользователь: <b>{user.full_name}</b> ({username_display})\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"💬 Сообщение:\n{message.text or message.caption or '(без текста)'}"
    )

    try:
        await bot.send_message(
            chat_id=SUPPORT_GROUP_ID,
            text=support_text,
            parse_mode="HTML",
            reply_markup=close_ticket_btn(ticket_id)
        )
        if message.content_type != "text":
            await message.forward(chat_id=SUPPORT_GROUP_ID)
    except Exception as e:
        logger.error(f"Failed to send ticket #{ticket_id} to support group: {e}")

    await message.answer(
        f"✅ Ваш запрос #{ticket_id} принят!\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n"
        "Вы можете продолжать писать — все сообщения будут переданы.",
        reply_markup=main_menu(is_admin=is_admin)
    )


@router.message(F.chat.id == SUPPORT_GROUP_ID, F.reply_to_message)
async def manager_reply(message: Message, bot: Bot):
    """Менеджер отвечает в группе поддержки на пересланное сообщение тикета —
    ответ автоматически уходит пользователю в личку."""
    replier = message.from_user
    if replier.id != OWNER_ID and not await is_manager(replier.id):
        return

    original = message.reply_to_message
    original_text = original.text or original.caption or ""

    user_id = None
    for line in original_text.split("\n"):
        if "🆔 ID:" in line and "<code>" in line:
            try:
                user_id = int(line.split("<code>")[1].split("</code>")[0])
            except (IndexError, ValueError):
                pass

    if not user_id:
        await message.reply("❌ Не удалось определить пользователя (ответьте на карточку тикета).")
        return

    try:
        reply_text = f"💬 <b>Ответ от поддержки:</b>\n\n{message.text or message.caption or ''}"
        if message.text:
            await bot.send_message(chat_id=user_id, text=reply_text, parse_mode="HTML")
        elif message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=f"💬 Ответ от поддержки:\n\n{message.caption or ''}"
            )
        elif message.document:
            await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=f"💬 Ответ от поддержки:\n\n{message.caption or ''}"
            )
        else:
            return

        await update_manager_activity(replier.id)
        try:
            await message.react([{"type": "emoji", "emoji": "✅"}])
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to send reply to user {user_id}: {e}")
        await message.reply(f"❌ Не удалось отправить сообщение пользователю {user_id}: {e}")


@router.callback_query(F.data.startswith("support:close:"))
async def close_support_ticket(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID and not await is_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[2])
    await close_ticket(ticket_id, callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Тикет #{ticket_id} закрыт менеджером {callback.from_user.full_name}")
    await callback.answer("Тикет закрыт")
