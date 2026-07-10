"""
config.py
Централизованная конфигурация приложения. Все значения читаются из переменных
окружения (.env локально, GitHub Secrets в проде). Никаких значений по
умолчанию для секретов — только для некритичных технических параметров.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
import os

# Загружаем .env, если он есть (локальная разработка). В GitHub Actions
# переменные уже будут в окружении через `env:` / Secrets, load_dotenv их не тронет.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_str(name: str, default: str) -> str:
    """Как os.getenv(name, default), но пустая строка тоже считается
    "не задано". Важно для GitHub Actions: ${{ vars.X }} для несуществующей
    переменной репозитория подставляется как пустая строка, а не отсутствует
    вовсе — обычный os.getenv(name, default) в этом случае вернул бы "",
    а не default."""
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val


def _get_list(name: str) -> list[int]:
    val = os.getenv(name, "")
    result: list[int] = []
    for chunk in val.split(","):
        chunk = chunk.strip()
        if chunk.isdigit() or (chunk.startswith("-") and chunk[1:].isdigit()):
            result.append(int(chunk))
    return result


@dataclass(frozen=True)
class Config:
    # --- Telegram (aiogram Bot API + функция Telegram Business "Чат-боты" /
    # Automated messages — НЕ Telethon-юзербот, НЕ api_id/api_hash) ---
    bot_token: str

    # --- ID владельца(ев) для админ-команд (доп. к тем, что определяются
    # автоматически через Business Connection) ---
    owner_ids: list[int] = field(default_factory=list)

    # --- AI provider: Google Gemini (текст, vision-OCR, аудио, генерация
    # изображений) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"

    # --- Storage ---
    db_path: str = str(BASE_DIR / "data" / "assistant.db")
    cache_dir: str = str(BASE_DIR / "assistant" / "cache" / "storage")
    log_dir: str = str(BASE_DIR / "logs")
    log_level: str = "INFO"

    # --- Runtime behaviour ---
    # Job в GitHub Actions живёт ограниченное время: слушаем события
    # столько секунд (long polling Bot API), затем аккуратно завершаемся.
    run_duration_seconds: int = 240
    reconnect_max_attempts: int = 5
    reconnect_base_delay: float = 2.0

    # --- Antispam ---
    antispam_max_messages: int = 8
    antispam_window_seconds: int = 10
    antispam_auto_blacklist: bool = True

    # --- Access control ---
    whitelist_mode: bool = False  # если True — отвечаем только whitelisted

    # --- Memory ---
    memory_context_messages: int = 20

    # --- Plugins ---
    plugins_enabled: bool = True

    @classmethod
    def load(cls) -> "Config":
        bot_token = os.getenv("BOT_TOKEN", "")

        missing = [name for name, val in (("BOT_TOKEN", bot_token),) if not val]
        if missing:
            sys.stderr.write(
                f"[config] Отсутствуют обязательные переменные окружения: {', '.join(missing)}. "
                "Создайте бота через @BotFather и задайте BOT_TOKEN в .env "
                "локально или в GitHub Secrets.\n"
            )
            raise SystemExit(78)  # EX_CONFIG

        return cls(
            bot_token=bot_token,
            owner_ids=_get_list("OWNER_IDS"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=_get_str("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_image_model=_get_str("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
            db_path=_get_str("DB_PATH", str(BASE_DIR / "data" / "assistant.db")),
            cache_dir=_get_str("CACHE_DIR", str(BASE_DIR / "assistant" / "cache" / "storage")),
            log_dir=_get_str("LOG_DIR", str(BASE_DIR / "logs")),
            log_level=_get_str("LOG_LEVEL", "INFO").upper(),
            run_duration_seconds=_get_int("RUN_DURATION_SECONDS", 240),
            reconnect_max_attempts=_get_int("RECONNECT_MAX_ATTEMPTS", 5),
            reconnect_base_delay=float(os.getenv("RECONNECT_BASE_DELAY", "2.0")),
            antispam_max_messages=_get_int("ANTISPAM_MAX_MESSAGES", 8),
            antispam_window_seconds=_get_int("ANTISPAM_WINDOW_SECONDS", 10),
            antispam_auto_blacklist=_get_bool("ANTISPAM_AUTO_BLACKLIST", True),
            whitelist_mode=_get_bool("WHITELIST_MODE", False),
            memory_context_messages=_get_int("MEMORY_CONTEXT_MESSAGES", 20),
            plugins_enabled=_get_bool("PLUGINS_ENABLED", True),
        )


config = Config.load())
