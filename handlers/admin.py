import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import OWNER_ID
from database.database import (
    get_users_count, get_messages_count, get_managers, get_chats,
    get_autoreplies, get_spam_filters, add_manager, remove_manager,
    add_chat, remove_chat, add_autoreply, remove_autoreply,
    add_spam_filter, remove_spam_filter, ban_user, unban_user,
    get_all_users, get_top_active_users, get_daily_activity,
    is_manager, get_user, get_ai_settings, update_ai_settings,
    clear_all_history, clear_history, block_contact, unblock_contact,
    set_contact_note, get_contact_note
)
from keyboards.inline import (
    main_admin_menu, back_to_admin, chats_menu, autoreplies_menu,
    autoreply_type_menu, managers_menu, manager_role_menu,
    broadcast_menu, antispam_menu, confirm_broadcast,
    ai_settings_menu, confirm_clear_history, history_menu,
    support_user_menu
)
from keyboards.reply import main_menu, cancel_menu
from utils.helpers import format_stats, format_analytics, broadcast_message, parse_buttons_from_text

logger = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    # Менеджеры
    add_manager_id = State()
    add_manager_role = State()
    # Чаты
    add_chat_id = State()
    # Автоответы
    ar_keyword = State()
    ar_type = State()
    ar_content = State()
    # Рассылка
    broadcast_text = State()
    broadcast_photo = State()
    broadcast_buttons_text = State()
    broadcast_confirm = State()
    # Спам
    spam_add_word = State()
    # Пользователи
    ban_user_id = State()
    unban_user_id = State()
    # ИИ
    ai_edit_prompt = State()
    ai_greeting_text = State()
    # Заметки / блокировка
    note_user_id = State()
    note_text = State()
    block_user_id = State()
    # История
    clear_history_chat_id = State()


def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


async def is_admin_or_manager(user_id: int) -> bool:
    return user_id == OWNER_ID or await is_manager(user_id)


# ── ТОЧКИ ВХОДА В ПАНЕЛЬ ─────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Панель администратора")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin_or_manager(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\nВыберите раздел:",
        reply_markup=main_admin_menu(),
        parse_mode="HTML"
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.business_connection_id:
        return  # В бизнес-чате /start игнорируем
    uid = message.from_user.id
    if is_admin(uid) or await is_manager(uid):
        await message.answer(
            f"👋 Привет! Я твой бизнес-ассистент.\n\n"
            f"Используй /admin для управления.",
            reply_markup=main_menu(is_admin=True)
        )
    else:
        await message.answer(
            "👋 Привет! Этот бот работает в фоновом режиме.\n\n"
            "Если у вас есть вопрос — нажмите кнопку ниже, и мы свяжемся с вами.",
            reply_markup=support_user_menu()
        )


@router.callback_query(F.data == "admin:main")
async def admin_main(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\n\nВыберите раздел:",
        reply_markup=main_admin_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# ── СТАТИСТИКА ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    users = await get_users_count()
    messages = await get_messages_count()
    managers = await get_managers()
    text = format_stats(users, messages, len(managers))
    await callback.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    daily = await get_daily_activity()
    top = await get_top_active_users(10)
    text = format_analytics(daily, top)
    await callback.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await callback.answer()


# ── AI SETTINGS ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:ai")
async def admin_ai(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    settings = await get_ai_settings()
    mode = settings.get("mode", "smart")
    auto = "✅" if settings.get("auto_reply_enabled", 1) else "❌"
    greet = "✅" if settings.get("greeting_enabled", 0) else "❌"
    mode_labels = {"smart": "🧠 Умный (БД→ИИ)", "always": "⚡ Всегда ИИ", "off": "🔕 Выключен"}
    text = (
        f"🧠 <b>Настройки ИИ</b>\n\n"
        f"Режим: <b>{mode_labels.get(mode, mode)}</b>\n"
        f"Автоответ: <b>{auto}</b>\n"
        f"Приветствие: <b>{greet}</b>\n\n"
        f"<i>Умный режим: сначала ищет в автоответах, потом ИИ.</i>\n"
        f"<i>Всегда ИИ: всегда генерирует ответ нейросетью.</i>"
    )
    await callback.message.edit_text(text, reply_markup=ai_settings_menu(settings), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai:mode_cycle")
async def ai_mode_cycle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    settings = await get_ai_settings()
    modes = ["smart", "always", "off"]
    current = settings.get("mode", "smart")
    next_mode = modes[(modes.index(current) + 1) % len(modes)]
    await update_ai_settings(mode=next_mode)
    settings["mode"] = next_mode
    mode_labels = {"smart": "🧠 Умный (БД→ИИ)", "always": "⚡ Всегда ИИ", "off": "🔕 Выключен"}
    await callback.answer(f"Режим: {mode_labels[next_mode]}", show_alert=False)
    # Обновляем меню
    settings = await get_ai_settings()
    auto = "✅" if settings.get("auto_reply_enabled", 1) else "❌"
    greet = "✅" if settings.get("greeting_enabled", 0) else "❌"
    text = (
        f"🧠 <b>Настройки ИИ</b>\n\n"
        f"Режим: <b>{mode_labels.get(next_mode, next_mode)}</b>\n"
        f"Автоответ: <b>{auto}</b>\n"
        f"Приветствие: <b>{greet}</b>"
    )
    await callback.message.edit_text(text, reply_markup=ai_settings_menu(settings), parse_mode="HTML")


@router.callback_query(F.data == "ai:toggle_auto")
async def ai_toggle_auto(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    settings = await get_ai_settings()
    new_val = 0 if settings.get("auto_reply_enabled", 1) else 1
    await update_ai_settings(auto_reply_enabled=new_val)
    await callback.answer("✅ Обновлено")
    settings = await get_ai_settings()
    await callback.message.edit_reply_markup(reply_markup=ai_settings_menu(settings))


@router.callback_query(F.data == "ai:toggle_greet")
async def ai_toggle_greet(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    settings = await get_ai_settings()
    new_val = 0 if settings.get("greeting_enabled", 0) else 1
    await update_ai_settings(greeting_enabled=new_val)
    await callback.answer("✅ Обновлено")
    settings = await get_ai_settings()
    await callback.message.edit_reply_markup(reply_markup=ai_settings_menu(settings))


@router.callback_query(F.data == "ai:edit_prompt")
async def ai_edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.ai_edit_prompt)
    settings = await get_ai_settings()
    current = settings.get("system_prompt") or "(пусто)"
    await callback.message.answer(
        f"✏️ <b>Текущий дополнительный промпт:</b>\n<code>{current[:1000]}</code>\n\n"
        f"Введи новый текст (дополнительные инструкции для ИИ). Пустое сообщение — сбросить:\n\n"
        f"❌ Отмена — /cancel",
        reply_markup=cancel_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.ai_edit_prompt)
async def ai_edit_prompt_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    new_prompt = message.text.strip() if message.text else ""
    await update_ai_settings(system_prompt=new_prompt)
    await state.clear()
    await message.answer(
        "✅ Системный промпт обновлён!\n\n"
        "ИИ теперь будет учитывать твои инструкции при ответах.",
        reply_markup=main_menu(is_admin=True)
    )


@router.callback_query(F.data == "ai:view_prompt")
async def ai_view_prompt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    settings = await get_ai_settings()
    from utils.ai import _build_system_prompt
    full = _build_system_prompt(settings)
    # Обрезаем для показа
    preview = full[:3000] + "..." if len(full) > 3000 else full
    await callback.message.answer(
        f"📋 <b>Полный системный промпт ИИ:</b>\n\n<code>{preview}</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ai:clear_all_history")
async def ai_clear_history_prompt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚠️ <b>Очистить ВСЮ историю диалогов?</b>\n\n"
        "ИИ забудет все предыдущие переписки с контактами.",
        reply_markup=confirm_clear_history(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ai:clear_history_confirm")
async def ai_clear_history_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await clear_all_history()
    await callback.message.edit_text(
        "✅ История диалогов очищена.",
        reply_markup=back_to_admin()
    )
    await callback.answer()


# ── ИСТОРИЯ ЧАТОВ (ADMIN) ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:history")
async def admin_history(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await callback.message.edit_text(
        "🗂 <b>История чатов</b>\n\n"
        "Введи команду:\n"
        "<code>/history_clear CHAT_ID</code> — очистить историю конкретного чата\n\n"
        "Или очисти всю историю в разделе 🧠 Настройки ИИ.",
        reply_markup=back_to_admin(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("history_clear"))
async def cmd_history_clear(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /history_clear CHAT_ID")
        return
    try:
        chat_id = int(parts[1])
        await clear_history(chat_id)
        await message.answer(f"✅ История чата <code>{chat_id}</code> очищена.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID чата.")


# ── ЗАМЕТКИ О КОНТАКТАХ ───────────────────────────────────────────────────────

@router.message(Command("note"))
async def cmd_note(message: Message, state: FSMContext):
    """Команда: /note USER_ID текст заметки"""
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование: <code>/note USER_ID текст заметки</code>\n"
            "Заметка будет видна только ИИ при ответах этому контакту.",
            parse_mode="HTML"
        )
        return
    try:
        uid = int(parts[1])
        note = parts[2]
        await set_contact_note(uid, note)
        await message.answer(f"✅ Заметка для <code>{uid}</code> сохранена.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID.")


@router.message(Command("get_note"))
async def cmd_get_note(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /get_note USER_ID")
        return
    try:
        uid = int(parts[1])
        note = await get_contact_note(uid)
        text = note if note else "(заметки нет)"
        await message.answer(f"📝 Заметка для <code>{uid}</code>:\n{text}", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID.")


# ── БЛОКИРОВКА КОНТАКТОВ ──────────────────────────────────────────────────────

@router.message(Command("block_contact"))
async def cmd_block_contact(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: /block_contact USER_ID [причина]")
        return
    try:
        uid = int(parts[1])
        reason = parts[2] if len(parts) > 2 else ""
        await block_contact(uid, reason)
        await message.answer(f"🚫 Контакт <code>{uid}</code> заблокирован для автоответов.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID.")


@router.message(Command("unblock_contact"))
async def cmd_unblock_contact(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unblock_contact USER_ID")
        return
    try:
        uid = int(parts[1])
        await unblock_contact(uid)
        await message.answer(f"✅ Контакт <code>{uid}</code> разблокирован.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID.")


# ── ЧАТЫ ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:chats")
async def admin_chats(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    chats = await get_chats()
    text = f"💬 <b>Подключённые чаты</b>\n\nВсего: {len(chats)}"
    await callback.message.edit_text(text, reply_markup=chats_menu(chats), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "chat:add")
async def chat_add_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminStates.add_chat_id)
    await callback.message.answer(
        "💬 Перешлите сообщение из нужного чата или введите ID вручную:",
        reply_markup=cancel_menu()
    )
    await callback.answer()


@router.message(AdminStates.add_chat_id)
async def chat_add_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    chat_id, title, chat_type = None, "Неизвестно", "unknown"
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title or "Без названия"
        chat_type = message.forward_from_chat.type
    elif message.text:
        try:
            chat_id = int(message.text.strip())
            title = f"Чат {chat_id}"
        except ValueError:
            await message.answer("❌ Неверный формат.")
            return
    if chat_id:
        await add_chat(chat_id, title, chat_type)
        await state.clear()
        await message.answer(
            f"✅ Чат <b>{title}</b> добавлен! ID: <code>{chat_id}</code>",
            reply_markup=main_menu(is_admin=True), parse_mode="HTML"
        )
    else:
        await message.answer("❌ Не удалось определить чат.")


@router.callback_query(F.data.startswith("chat:remove:"))
async def chat_remove(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    chat_id = int(callback.data.split(":")[2])
    await remove_chat(chat_id)
    chats = await get_chats()
    await callback.message.edit_text(
        f"💬 <b>Подключённые чаты</b>\n\nВсего: {len(chats)}",
        reply_markup=chats_menu(chats), parse_mode="HTML"
    )
    await callback.answer("✅ Чат удалён")


# ── АВТООТВЕТЫ ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:autoreplies")
async def admin_autoreplies(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    ars = await get_autoreplies()
    await callback.message.edit_text(
        f"🤖 <b>Автоответы</b>\n\nВсего: {len(ars)}",
        reply_markup=autoreplies_menu(ars), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ar:add")
async def ar_add_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminStates.ar_keyword)
    await callback.message.answer(
        "🔑 Введите ключевое слово или фразу для автоответа:",
        reply_markup=cancel_menu()
    )
    await callback.answer()


@router.message(AdminStates.ar_keyword)
async def ar_keyword_received(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    await state.update_data(keyword=message.text)
    await state.set_state(AdminStates.ar_type)
    await message.answer(
        f"✅ Ключ: <b>{message.text}</b>\n\nВыберите тип ответа:",
        reply_markup=autoreply_type_menu(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ar:type:"))
async def ar_type_selected(callback: CallbackQuery, state: FSMContext):
    rtype = callback.data.split(":")[2]
    await state.update_data(reply_type=rtype)
    await state.set_state(AdminStates.ar_content)
    prompts = {
        "text": "📝 Введите текст ответа:",
        "photo": "🖼 Отправьте фото с подписью (или без):",
        "video": "🎥 Отправьте видео с подписью (или без):",
        "document": "📁 Отправьте файл с подписью (или без):",
    }
    await callback.message.answer(prompts.get(rtype, "Введите ответ:"), reply_markup=cancel_menu())
    await callback.answer()


@router.message(AdminStates.ar_content)
async def ar_content_received(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    data = await state.get_data()
    keyword = data["keyword"]
    rtype = data["reply_type"]
    file_id = reply_text = caption = None
    if rtype == "text":
        reply_text = message.text
    elif rtype == "photo" and message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption or ""
        reply_text = caption
    elif rtype == "video" and message.video:
        file_id = message.video.file_id
        caption = message.caption or ""
        reply_text = caption
    elif rtype == "document" and message.document:
        file_id = message.document.file_id
        caption = message.caption or ""
        reply_text = caption
    else:
        await message.answer("❌ Неверный тип. Попробуйте снова.")
        return
    await add_autoreply(keyword, reply_text or "", rtype, file_id, caption)
    await state.clear()
    await message.answer(
        f"✅ Автоответ добавлен!\n🔑 Ключ: <b>{keyword}</b>",
        reply_markup=main_menu(is_admin=True), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ar:remove:"))
async def ar_remove(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    ar_id = int(callback.data.split(":")[2])
    await remove_autoreply(ar_id)
    ars = await get_autoreplies()
    await callback.message.edit_text(
        f"🤖 <b>Автоответы</b>\n\nВсего: {len(ars)}",
        reply_markup=autoreplies_menu(ars), parse_mode="HTML"
    )
    await callback.answer("✅ Удалён")


# ── МЕНЕДЖЕРЫ ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:managers")
async def admin_managers(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    managers = await get_managers()
    await callback.message.edit_text(
        f"👥 <b>Менеджеры</b>\n\nВсего: {len(managers)}",
        reply_markup=managers_menu(managers), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "mgr:add")
async def manager_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.add_manager_id)
    await callback.message.answer(
        "👤 Введите Telegram ID нового менеджера:",
        reply_markup=cancel_menu()
    )
    await callback.answer()


@router.message(AdminStates.add_manager_id)
async def manager_add_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    try:
        mgr_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID.")
        return
    user_data = await get_user(mgr_id)
    full_name = user_data["full_name"] if user_data else "Неизвестно"
    await state.update_data(mgr_id=mgr_id, full_name=full_name)
    await message.answer(
        f"Выберите роль для <b>{full_name}</b>:",
        reply_markup=manager_role_menu(mgr_id), parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("mgr:role:"))
async def manager_set_role(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    parts = callback.data.split(":")
    mgr_id, role = int(parts[2]), parts[3]
    user_data = await get_user(mgr_id)
    full_name = user_data["full_name"] if user_data else "Неизвестно"
    username = user_data["username"] if user_data else ""
    await add_manager(mgr_id, username, full_name, role)
    managers = await get_managers()
    await callback.message.edit_text(
        f"✅ Менеджер <b>{full_name}</b> добавлен как <b>{role}</b>.\n\n"
        f"👥 <b>Менеджеры</b>\n\nВсего: {len(managers)}",
        reply_markup=managers_menu(managers), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgr:remove:"))
async def manager_remove(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    mgr_id = int(callback.data.split(":")[2])
    await remove_manager(mgr_id)
    managers = await get_managers()
    await callback.message.edit_text(
        f"✅ Менеджер удалён.\n\n👥 <b>Менеджеры</b>\n\nВсего: {len(managers)}",
        reply_markup=managers_menu(managers), parse_mode="HTML"
    )
    await callback.answer("✅ Удалён")


@router.callback_query(F.data.startswith("mgr:info:"))
async def manager_info(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    mgr_id = int(callback.data.split(":")[2])
    managers = await get_managers()
    mgr = next((m for m in managers if m["telegram_id"] == mgr_id), None)
    if not mgr:
        await callback.answer("Менеджер не найден.", show_alert=True)
        return
    text = (
        f"👤 <b>Менеджер</b>\n\n"
        f"Имя: <b>{mgr['full_name']}</b>\n"
        f"Username: @{mgr['username'] or 'нет'}\n"
        f"ID: <code>{mgr['telegram_id']}</code>\n"
        f"Роль: <b>{mgr['role']}</b>\n"
        f"Обработано: <b>{mgr['messages_handled']}</b> сообщений\n"
        f"Добавлен: {mgr['added_at']}"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ── РАССЫЛКА ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await callback.message.edit_text(
        "📣 <b>Рассылка</b>\n\nВыберите тип:",
        reply_markup=broadcast_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:text")
async def broadcast_text_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_text)
    await state.update_data(broadcast_type="text")
    await callback.message.answer("📝 Введите текст рассылки:", reply_markup=cancel_menu())
    await callback.answer()


@router.callback_query(F.data == "broadcast:photo")
async def broadcast_photo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_photo)
    await state.update_data(broadcast_type="photo")
    await callback.message.answer("🖼 Отправьте фото:", reply_markup=cancel_menu())
    await callback.answer()


@router.callback_query(F.data == "broadcast:buttons")
async def broadcast_buttons_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_buttons_text)
    await state.update_data(broadcast_type="buttons")
    await callback.message.answer(
        "📝 Текст + кнопки.\nФормат кнопок: <code>[Текст](https://url)</code>",
        reply_markup=cancel_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.broadcast_text)
@router.message(AdminStates.broadcast_buttons_text)
async def broadcast_text_received(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    data = await state.get_data()
    btype = data.get("broadcast_type", "text")
    text, markup = parse_buttons_from_text(message.text) if btype == "buttons" else (message.text, None)
    await state.update_data(
        broadcast_text=text, has_buttons=(markup is not None),
        parsed_markup_data=message.text if btype == "buttons" else None
    )
    await state.set_state(AdminStates.broadcast_confirm)
    users = await get_all_users()
    await message.answer(
        f"📣 <b>Предпросмотр:</b>\n\n{text}\n\n👥 Получателей: <b>{len(users)}</b>\n\nОтправить?",
        reply_markup=confirm_broadcast(len(users)), parse_mode="HTML"
    )


@router.message(AdminStates.broadcast_photo)
async def broadcast_photo_received(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    if not message.photo:
        await message.answer("❌ Отправьте фото.")
        return
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    await state.update_data(broadcast_photo=file_id, broadcast_text=caption)
    await state.set_state(AdminStates.broadcast_confirm)
    users = await get_all_users()
    await message.answer(
        f"🖼 Фото готово.\n👥 Получателей: <b>{len(users)}</b>\n\nОтправить?",
        reply_markup=confirm_broadcast(len(users)), parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast:confirm")
async def broadcast_confirm_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    users = await get_all_users()
    user_ids = [u["telegram_id"] for u in users]
    text = data.get("broadcast_text", "")
    photo = data.get("broadcast_photo")
    markup = None
    if data.get("has_buttons") and data.get("parsed_markup_data"):
        _, markup = parse_buttons_from_text(data["parsed_markup_data"])
    await callback.message.edit_text("⏳ Выполняю рассылку...")
    result = await broadcast_message(bot, user_ids, text, photo, markup)
    await callback.message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n✔️ Успешно: <b>{result['success']}</b>\n❌ Ошибок: <b>{result['failed']}</b>",
        reply_markup=back_to_admin(), parse_mode="HTML"
    )
    await callback.answer()


# ── АНТИСПАМ ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:antispam")
async def admin_antispam(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    filters = await get_spam_filters()
    await callback.message.edit_text(
        f"🛡 <b>Антиспам</b>\n\nАктивных фильтров: {len(filters)}",
        reply_markup=antispam_menu(filters), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("spam:add:"))
async def spam_add_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    ftype = callback.data.split(":")[2]
    await state.set_state(AdminStates.spam_add_word)
    await state.update_data(spam_type=ftype)
    prompt = "🔗 Введите домен (например: bit.ly):" if ftype == "links" else "🤬 Введите запрещённое слово:"
    await callback.message.answer(prompt, reply_markup=cancel_menu())
    await callback.answer()


@router.message(AdminStates.spam_add_word)
async def spam_add_word_handler(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    data = await state.get_data()
    await add_spam_filter(data["spam_type"], message.text.strip())
    await state.clear()
    await message.answer(
        f"✅ Фильтр добавлен: <code>{message.text.strip()}</code>",
        reply_markup=main_menu(is_admin=True), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("spam:remove:"))
async def spam_remove(callback: CallbackQuery):
    if not await is_admin_or_manager(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    fid = int(callback.data.split(":")[2])
    await remove_spam_filter(fid)
    filters = await get_spam_filters()
    await callback.message.edit_text(
        f"🛡 <b>Антиспам</b>\n\nАктивных фильтров: {len(filters)}",
        reply_markup=antispam_menu(filters), parse_mode="HTML"
    )
    await callback.answer("✅ Удалён")


# ── ПОЛЬЗОВАТЕЛИ ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="users:ban"),
        InlineKeyboardButton(text="✅ Разблокировать", callback_data="users:unban"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    await callback.message.edit_text(
        "🔒 <b>Управление пользователями</b>\n\n"
        "Также: /block_contact USER_ID — заблокировать автоответ\n"
        "/note USER_ID текст — заметка для ИИ",
        reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "users:ban")
async def ban_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.ban_user_id)
    await callback.message.answer("🚫 Введите ID:", reply_markup=cancel_menu())
    await callback.answer()


@router.message(AdminStates.ban_user_id)
async def ban_user_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    try:
        uid = int(message.text.strip())
        await ban_user(uid)
        await state.clear()
        await message.answer(f"🚫 Пользователь <code>{uid}</code> заблокирован.", reply_markup=main_menu(is_admin=True), parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Введите числовой ID.")


@router.callback_query(F.data == "users:unban")
async def unban_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только владелец.", show_alert=True)
        return
    await state.set_state(AdminStates.unban_user_id)
    await callback.message.answer("✅ Введите ID:", reply_markup=cancel_menu())
    await callback.answer()


@router.message(AdminStates.unban_user_id)
async def unban_user_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu(is_admin=True))
        return
    try:
        uid = int(message.text.strip())
        await unban_user(uid)
        await state.clear()
        await message.answer(f"✅ Пользователь <code>{uid}</code> разблокирован.", reply_markup=main_menu(is_admin=True), parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Введите числовой ID.")
