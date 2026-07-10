"""
plugins/loader.py
Сканирует директорию assistant/plugins/, импортирует все .py модули
(кроме __init__.py, base.py, loader.py) и регистрирует найденные в них
классы-наследники Plugin.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

from aiogram import Dispatcher

from assistant.logger import log
from assistant.plugins.base import Plugin

_EXCLUDED_MODULES = {"__init__", "base", "loader"}


def discover_plugins() -> list[type[Plugin]]:
    package_dir = Path(__file__).parent
    package_name = "assistant.plugins"
    found: list[type[Plugin]] = []

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in _EXCLUDED_MODULES:
            continue
        try:
            module = importlib.import_module(f"{package_name}.{module_info.name}")
        except Exception as exc:  # noqa: BLE001
            log.error("Не удалось загрузить плагин {}: {}", module_info.name, exc)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin:
                found.append(obj)

    return found


def load_plugins(dp: Dispatcher) -> list[Plugin]:
    instances: list[Plugin] = []
    for plugin_cls in discover_plugins():
        try:
            instance = plugin_cls()
            instance.register(dp)
            instances.append(instance)
            log.info("Плагин '{}' загружен и зарегистрирован.", instance.name)
        except Exception as exc:  # noqa: BLE001
            log.error("Ошибка инициализации плагина {}: {}", plugin_cls.__name__, exc)
    return instances
