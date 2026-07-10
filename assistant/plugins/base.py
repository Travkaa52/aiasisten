"""
plugins/base.py
Базовый интерфейс плагина. Плагин — это модуль в assistant/plugins/,
экспортирующий класс-наследник Plugin. Загрузчик (plugins/loader.py)
автоматически находит такие классы и вызывает register(client).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from telethon import TelegramClient


class Plugin(ABC):
    name: str = "unnamed_plugin"
    description: str = ""

    @abstractmethod
    def register(self, client: TelegramClient) -> None:
        """Регистрирует event handlers плагина на клиенте Telethon."""
        raise NotImplementedError
