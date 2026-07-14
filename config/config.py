import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: str = "0") -> int:
    """Безопасно читает int-переменную окружения.
    Трактует и отсутствующую, и пустую строку (VAR=) как значение по умолчанию,
    чтобы не падать с невнятным ValueError при незаполненном .env/секрете."""
    raw = os.getenv(name) or default
    try:
        return int(raw)
    except ValueError:
        print(
            f"❌ Переменная окружения {name}='{raw}' не является числом. "
            f"Проверь .env (или Secrets в GitHub Actions).",
            file=sys.stderr,
        )
        raise


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = _int_env("OWNER_ID")
SUPPORT_GROUP_ID: int = _int_env("SUPPORT_GROUP_ID")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
GEMINI_KEY: str = os.getenv("GEMINI_KEY", "")

# ── Модель Gemini ────────────────────────────────────────────────────────
# По умолчанию — Gemini 3.5 Flash: самая мощная модель линейки Flash,
# полностью бесплатная по API (free tier) на июль 2026.
# Если основная модель недоступна (лимиты/регион/устарела) — автоматически
# используется резервная модель GEMINI_MODEL_FALLBACK.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"
GEMINI_MODEL_FALLBACK: str = os.getenv("GEMINI_MODEL_FALLBACK") or "gemini-2.5-flash"

# ── Имя владельца бота (используется в системном промпте) ──────────────────
OWNER_NAME: str = os.getenv("OWNER_NAME") or "Владелец"
BUSINESS_NAME: str = os.getenv("BUSINESS_NAME") or "Наша компания"
BUSINESS_DESCRIPTION: str = os.getenv(
    "BUSINESS_DESCRIPTION"
) or "Мы занимаемся продажей товаров и услуг высокого качества."

# ── Язык ответов ИИ ────────────────────────────────────────────────────────
AI_LANGUAGE: str = os.getenv("AI_LANGUAGE") or "ru"

# ── Макс. сообщений истории, которые мы шлём Gemini ──────────────────────
AI_HISTORY_DEPTH: int = _int_env("AI_HISTORY_DEPTH", "10")

# ── Порог «долгой паузы» (в секундах) для сброса контекста ───────────────
SESSION_TIMEOUT: int = _int_env("SESSION_TIMEOUT", "3600")

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN is not set. Заполни .env (см. .env.example) либо, если "
        "используешь GitHub Actions — добавь секрет BOT_TOKEN в "
        "Settings → Secrets and variables → Actions."
    )
if not OWNER_ID:
    raise ValueError(
        "OWNER_ID is not set. Заполни .env (см. .env.example) либо, если "
        "используешь GitHub Actions — добавь секрет OWNER_ID в "
        "Settings → Secrets and variables → Actions."
    )
