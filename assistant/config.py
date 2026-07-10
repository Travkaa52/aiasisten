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
    # --- Telegram (Telethon user-account, НЕ Bot API) ---
    api_id: int
    api_hash: str
    session_string: str

    # --- Владелец аккаунта (для админ-команд, DND, заметок и т.д.) ---
    owner_ids: list[int] = field(default_factory=list)

    # --- AI provider ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    openai_api_key: str = ""  # используется для генерации изображений и transcribe
    openai_image_model: str = "dall-e-3"
    openai_whisper_model: str = "whisper-1"

    # --- Storage ---
    db_path: str = str(BASE_DIR / "data" / "assistant.db")
    cache_dir: str = str(BASE_DIR / "assistant" / "cache" / "storage")
    log_dir: str = str(BASE_DIR / "logs")
    log_level: str = "INFO"

    # --- Runtime behaviour ---
    # Job в GitHub Actions живёт ограниченное время: слушаем события
    # столько секунд, затем аккуратно завершаемся (чтобы не упереться
    # в лимит воркфлоу и не оставить оборванное TCP-соединение).
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
        api_id_raw = os.getenv("API_ID", "")
        api_hash = os.getenv("API_HASH", "")
        session_string = os.getenv("SESSION", "")

        missing = [
            name
            for name, val in (
                ("API_ID", api_id_raw),
                ("API_HASH", api_hash),
                ("SESSION", session_string),
            )
            if not val
        ]
        if missing:
            sys.stderr.write(
                f"[config] Отсутствуют обязательные переменные окружения: {', '.join(missing)}. "
                "Задайте их в .env локально или в GitHub Secrets.\n"
            )
            raise SystemExit(78)  # EX_CONFIG

        try:
            api_id = int(api_id_raw)
        except ValueError:
            sys.stderr.write("[config] API_ID должен быть целым числом.\n")
            raise SystemExit(78)

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            owner_ids=_get_list("OWNER_IDS"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3"),
            openai_whisper_model=os.getenv("OPENAI_WHISPER_MODEL", "whisper-1"),
            db_path=os.getenv("DB_PATH", str(BASE_DIR / "data" / "assistant.db")),
            cache_dir=os.getenv("CACHE_DIR", str(BASE_DIR / "assistant" / "cache" / "storage")),
            log_dir=os.getenv("LOG_DIR", str(BASE_DIR / "logs")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
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


config = Config.load()
