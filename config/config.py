import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
SUPPORT_GROUP_ID: int = int(os.getenv("SUPPORT_GROUP_ID", "0"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
GEMINI_KEY: str = os.getenv("GEMINI_KEY", "")

# ── Модель Gemini ────────────────────────────────────────────────────────
# По умолчанию — Gemini 3.5 Flash: самая мощная модель линейки Flash,
# полностью бесплатная по API (free tier) на июль 2026.
# Если основная модель недоступна (лимиты/регион/устарела) — автоматически
# используется резервная модель GEMINI_MODEL_FALLBACK.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_MODEL_FALLBACK: str = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-2.5-flash")

# ── Имя владельца бота (используется в системном промпте) ──────────────────
OWNER_NAME: str = os.getenv("OWNER_NAME", "Владелец")
BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Наша компания")
BUSINESS_DESCRIPTION: str = os.getenv(
    "BUSINESS_DESCRIPTION",
    "Мы занимаемся продажей товаров и услуг высокого качества."
)

# ── Язык ответов ИИ ────────────────────────────────────────────────────────
AI_LANGUAGE: str = os.getenv("AI_LANGUAGE", "ru")

# ── Макс. сообщений истории, которые мы шлём Gemini ──────────────────────
AI_HISTORY_DEPTH: int = int(os.getenv("AI_HISTORY_DEPTH", "10"))

# ── Порог «долгой паузы» (в секундах) для сброса контекста ───────────────
SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "3600"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")
if not OWNER_ID:
    raise ValueError("OWNER_ID is not set in .env file")
