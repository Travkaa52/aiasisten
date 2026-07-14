import aiosqlite
import logging
import json
from datetime import datetime
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                is_banned INTEGER DEFAULT 0,
                tariff TEXT DEFAULT 'free',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS managers (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'manager',
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                messages_handled INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE NOT NULL,
                title TEXT,
                chat_type TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS autoreply (
                id INTEGER PRIMARY KEY,
                keyword TEXT NOT NULL,
                reply_text TEXT,
                reply_type TEXT DEFAULT 'text',
                file_id TEXT,
                caption TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                chat_id INTEGER,
                message_text TEXT,
                direction TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS spam_filter (
                id INTEGER PRIMARY KEY,
                filter_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS muted_users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                muted_until TEXT,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                manager_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                system_prompt TEXT,
                mode TEXT DEFAULT 'smart',
                auto_reply_enabled INTEGER DEFAULT 1,
                greeting_enabled INTEGER DEFAULT 1,
                greeting_text TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS blocked_contacts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS contact_notes (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                note TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Вставляем дефолтные настройки ИИ если их ещё нет
        await db.execute("""
            INSERT OR IGNORE INTO ai_settings (id, system_prompt, mode)
            VALUES (1, '', 'smart')
        """)
        await db.commit()
    logger.info("Database initialized successfully")


# ──────────────────────────────────────────────────────────────────────────────
# USERS
# ──────────────────────────────────────────────────────────────────────────────

async def add_user(telegram_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
            (telegram_id, username, full_name)
        )
        await db.execute(
            "UPDATE users SET username=?, full_name=?, last_active=CURRENT_TIMESTAMP WHERE telegram_id=?",
            (username, full_name, telegram_id)
        )
        await db.commit()


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)) as c:
            return await c.fetchone()


async def get_all_users():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_banned=0") as c:
            return await c.fetchall()


async def get_users_count():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            row = await c.fetchone()
            return row[0] if row else 0


async def get_messages_count():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM messages") as c:
            row = await c.fetchone()
            return row[0] if row else 0


async def get_top_active_users(limit: int = 10):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.telegram_id, u.username, u.full_name, COUNT(m.id) as msg_count
            FROM users u
            LEFT JOIN messages m ON u.telegram_id = m.user_id
            GROUP BY u.telegram_id
            ORDER BY msg_count DESC LIMIT ?
        """, (limit,)) as c:
            return await c.fetchall()


async def get_daily_activity():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM messages GROUP BY DATE(created_at)
            ORDER BY day DESC LIMIT 7
        """) as c:
            return await c.fetchall()


async def log_message(user_id: int, text: str, direction: str = "incoming", chat_id: int = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO messages (user_id, chat_id, message_text, direction) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, text, direction)
        )
        await db.commit()


async def ban_user(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE telegram_id=?", (telegram_id,))
        await db.commit()


async def unban_user(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE telegram_id=?", (telegram_id,))
        await db.commit()


async def is_banned(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE telegram_id=?", (telegram_id,)) as c:
            row = await c.fetchone()
            return row and row[0] == 1


# ──────────────────────────────────────────────────────────────────────────────
# MANAGERS
# ──────────────────────────────────────────────────────────────────────────────

async def add_manager(telegram_id: int, username: str, full_name: str, role: str = "manager"):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO managers (telegram_id, username, full_name, role) VALUES (?, ?, ?, ?)",
            (telegram_id, username, full_name, role)
        )
        await db.commit()


async def remove_manager(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM managers WHERE telegram_id=?", (telegram_id,))
        await db.commit()


async def get_managers():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM managers") as c:
            return await c.fetchall()


async def is_manager(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT id FROM managers WHERE telegram_id=?", (telegram_id,)) as c:
            return await c.fetchone() is not None


async def update_manager_activity(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE managers SET messages_handled = messages_handled + 1 WHERE telegram_id=?",
            (telegram_id,)
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# CHATS
# ──────────────────────────────────────────────────────────────────────────────

async def add_chat(chat_id: int, title: str, chat_type: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO chats (chat_id, title, chat_type) VALUES (?, ?, ?)",
            (chat_id, title, chat_type)
        )
        await db.commit()


async def remove_chat(chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))
        await db.commit()


async def get_chats():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chats") as c:
            return await c.fetchall()


# ──────────────────────────────────────────────────────────────────────────────
# AUTOREPLIES
# ──────────────────────────────────────────────────────────────────────────────

async def add_autoreply(keyword: str, reply_text: str, reply_type: str = "text",
                        file_id: str = None, caption: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO autoreply (keyword, reply_text, reply_type, file_id, caption) VALUES (?, ?, ?, ?, ?)",
            (keyword, reply_text, reply_type, file_id, caption)
        )
        await db.commit()


async def remove_autoreply(autoreply_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM autoreply WHERE id=?", (autoreply_id,))
        await db.commit()


async def get_autoreplies():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM autoreply") as c:
            return await c.fetchall()


async def find_autoreply(text: str):
    text_lower = text.lower()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM autoreply") as c:
            rows = await c.fetchall()
    for row in rows:
        if row["keyword"].lower() in text_lower:
            return row
    return None


# ──────────────────────────────────────────────────────────────────────────────
# SPAM FILTER
# ──────────────────────────────────────────────────────────────────────────────

async def add_spam_filter(filter_type: str, value: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO spam_filter (filter_type, value) VALUES (?, ?)", (filter_type, value))
        await db.commit()


async def remove_spam_filter(filter_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM spam_filter WHERE id=?", (filter_id,))
        await db.commit()


async def get_spam_filters():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM spam_filter") as c:
            return await c.fetchall()


# ──────────────────────────────────────────────────────────────────────────────
# SUPPORT TICKETS
# ──────────────────────────────────────────────────────────────────────────────

async def create_ticket(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("INSERT INTO support_tickets (user_id) VALUES (?)", (user_id,))
        await db.commit()
        return cursor.lastrowid


async def close_ticket(ticket_id: int, manager_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE support_tickets SET status='closed', manager_id=?, closed_at=CURRENT_TIMESTAMP WHERE id=?",
            (manager_id, ticket_id)
        )
        await db.commit()


async def get_open_ticket(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_tickets WHERE user_id=? AND status='open'", (user_id,)
        ) as c:
            return await c.fetchone()


# ──────────────────────────────────────────────────────────────────────────────
# AI SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

async def get_ai_settings() -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ai_settings WHERE id=1") as c:
            row = await c.fetchone()
            if row:
                return dict(row)
            return {
                "system_prompt": "",
                "mode": "smart",
                "auto_reply_enabled": 1,
                "greeting_enabled": 0,
                "greeting_text": "",
            }


async def update_ai_settings(**kwargs):
    """Обновляем любые поля в ai_settings."""
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [1]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE ai_settings SET {fields}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            values
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATION HISTORY  (хранит историю диалогов по chat_id)
# ──────────────────────────────────────────────────────────────────────────────

async def add_to_history(chat_id: int, role: str, content: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_history (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        await db.commit()


async def get_history(chat_id: int, limit: int = 10) -> list[dict]:
    """Возвращает последние N сообщений в формате [{role, content}, ...]."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT role, content FROM (
                SELECT role, content, created_at FROM conversation_history
                WHERE chat_id=?
                ORDER BY created_at DESC LIMIT ?
            ) ORDER BY created_at ASC
        """, (chat_id, limit)) as c:
            rows = await c.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def clear_history(chat_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM conversation_history WHERE chat_id=?", (chat_id,))
        await db.commit()


async def clear_all_history():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM conversation_history")
        await db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# BLOCKED CONTACTS & NOTES
# ──────────────────────────────────────────────────────────────────────────────

async def block_contact(user_id: int, reason: str = ""):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_contacts (user_id, reason) VALUES (?, ?)",
            (user_id, reason)
        )
        await db.commit()


async def unblock_contact(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM blocked_contacts WHERE user_id=?", (user_id,))
        await db.commit()


async def is_contact_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT id FROM blocked_contacts WHERE user_id=?", (user_id,)) as c:
            return await c.fetchone() is not None


async def set_contact_note(user_id: int, note: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO contact_notes (user_id, note, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (user_id, note)
        )
        await db.commit()


async def get_contact_note(user_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT note FROM contact_notes WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else ""
