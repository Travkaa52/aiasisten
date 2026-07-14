from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        InlineKeyboardButton(text="📈 Аналитика", callback_data="admin:analytics"),
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Автоответы", callback_data="admin:autoreplies"),
        InlineKeyboardButton(text="🧠 Настройки ИИ", callback_data="admin:ai"),
    )
    builder.row(
        InlineKeyboardButton(text="💬 Чаты", callback_data="admin:chats"),
        InlineKeyboardButton(text="👥 Менеджеры", callback_data="admin:managers"),
    )
    builder.row(
        InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="🛡 Антиспам", callback_data="admin:antispam"),
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton(text="🗂 История чатов", callback_data="admin:history"),
    )
    return builder.as_markup()


def back_to_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin:main")
    return builder.as_markup()


# ── AI SETTINGS ───────────────────────────────────────────────────────────────

def ai_settings_menu(settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    mode = settings.get("mode", "smart")
    auto = settings.get("auto_reply_enabled", 1)
    greet = settings.get("greeting_enabled", 0)

    mode_labels = {"smart": "🧠 Умный", "always": "⚡ Всегда", "off": "🔕 Выкл"}
    builder.row(
        InlineKeyboardButton(
            text=f"Режим: {mode_labels.get(mode, mode)}",
            callback_data="ai:mode_cycle"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if auto else '❌'} Автоответ на сообщения",
            callback_data="ai:toggle_auto"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if greet else '❌'} Приветствие новых",
            callback_data="ai:toggle_greet"
        )
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить промпт", callback_data="ai:edit_prompt"),
        InlineKeyboardButton(text="👁 Просмотр промпта", callback_data="ai:view_prompt"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить всю историю", callback_data="ai:clear_all_history"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def confirm_clear_history() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚠️ Да, очистить", callback_data="ai:clear_history_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:ai"),
    )
    return builder.as_markup()


# ── CHATS ─────────────────────────────────────────────────────────────────────

def chats_menu(chats: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for chat in chats:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {chat['title']}",
                callback_data=f"chat:remove:{chat['chat_id']}"
            )
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить чат", callback_data="chat:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


# ── AUTOREPLIES ───────────────────────────────────────────────────────────────

def autoreplies_menu(autoreplies: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ar in autoreplies:
        builder.row(
            InlineKeyboardButton(
                text=f"🔑 {ar['keyword'][:20]}",
                callback_data=f"ar:view:{ar['id']}"
            ),
            InlineKeyboardButton(text="❌", callback_data=f"ar:remove:{ar['id']}"),
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить автоответ", callback_data="ar:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def autoreply_type_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Текст", callback_data="ar:type:text"),
        InlineKeyboardButton(text="🖼 Фото", callback_data="ar:type:photo"),
    )
    builder.row(
        InlineKeyboardButton(text="🎥 Видео", callback_data="ar:type:video"),
        InlineKeyboardButton(text="📁 Файл", callback_data="ar:type:document"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:autoreplies"))
    return builder.as_markup()


# ── MANAGERS ──────────────────────────────────────────────────────────────────

def managers_menu(managers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in managers:
        name = m["full_name"] or m["username"] or str(m["telegram_id"])
        builder.row(
            InlineKeyboardButton(text=f"👤 {name} [{m['role']}]", callback_data=f"mgr:info:{m['telegram_id']}"),
            InlineKeyboardButton(text="❌", callback_data=f"mgr:remove:{m['telegram_id']}"),
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить менеджера", callback_data="mgr:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def manager_role_menu(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Менеджер", callback_data=f"mgr:role:{telegram_id}:manager"),
        InlineKeyboardButton(text="⭐ Старший", callback_data=f"mgr:role:{telegram_id}:senior"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:managers"))
    return builder.as_markup()


# ── BROADCAST ─────────────────────────────────────────────────────────────────

def broadcast_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Текст", callback_data="broadcast:text"),
        InlineKeyboardButton(text="🖼 Фото", callback_data="broadcast:photo"),
    )
    builder.row(
        InlineKeyboardButton(text="🎨 Текст + кнопки", callback_data="broadcast:buttons"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def confirm_broadcast(total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Отправить ({total} польз.)", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast"),
    )
    return builder.as_markup()


# ── ANTISPAM ──────────────────────────────────────────────────────────────────

def antispam_menu(filters: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔗 Фильтр ссылок", callback_data="spam:add:links"),
        InlineKeyboardButton(text="🤬 Запрещённые слова", callback_data="spam:add:words"),
    )
    for f in filters:
        builder.row(
            InlineKeyboardButton(
                text=f"{'🔗' if f['filter_type'] == 'links' else '🤬'} {f['value'][:25]}",
                callback_data=f"spam:remove:{f['id']}"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()


# ── SUPPORT ───────────────────────────────────────────────────────────────────

def support_user_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📨 Написать в поддержку", callback_data="support:start")
    return builder.as_markup()


def close_ticket_btn(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Закрыть тикет", callback_data=f"support:close:{ticket_id}")
    return builder.as_markup()


# ── HISTORY ───────────────────────────────────────────────────────────────────

def history_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗑 Очистить историю чата", callback_data="history:clear_prompt"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main"))
    return builder.as_markup()
