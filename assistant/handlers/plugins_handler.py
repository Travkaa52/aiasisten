"""
handlers/plugins_handler.py
Тонкая обёртка, вызывающая plugins/loader.py — вынесена в handlers/,
чтобы main.py регистрировал все обработчики единообразно.
"""

from __future__ import annotations

from aiogram import Dispatcher

from assistant.config import config
from assistant.logger import log
from assistant.plugins.loader import load_plugins


def register_plugins(dp: Dispatcher) -> None:
    if not config.plugins_enabled:
        log.info("Плагины отключены конфигурацией (PLUGINS_ENABLED=false).")
        return
    instances = load_plugins(dp)
    log.info("Загружено плагинов: {}", len(instances))
