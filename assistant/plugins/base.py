"""
plugins/base.py
Базовый интерфейс плагина. Плагин — это модуль в assistant/plugins/,
экспортирующий класс-наследник Plugin. Загрузчик (plugins/loader.py)
автоматически находит такие классы и вызывает register(dp).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiogram import Dispatcher


class Plugin(ABC):
    name: str = "unnamed_plugin"
    description: str = ""

    @abstractmethod
    def register(self, dp: Dispatcher) -> None:
        """Регистрирует event handlers плагина на диспетчере aiogram
        (обычно через отдельный Router, добавленный в dp.include_router)."""
        raise NotImplementedError
