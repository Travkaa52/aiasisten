"""
plugins/ping_plugin.py
Пример полностью рабочего плагина: команда /ping измеряет задержку
между отправкой и редактированием сообщения (round-trip до Telegram).
Работает как в обычных чатах, так и в чатах, подключённых через функцию
Telegram Business «Чат-боты» (business_message).
"""

from __future__ import annotations

import time

from aiogram import Dispatcher, F, Router
from aiogram.types import Message

from assistant.handlers.access import is_message_from_owner
from assistant.plugins.base import Plugin


class PingPlugin(Plugin):
    name = "ping"
    description = "Проверка задержки ответа ассистента (/ping)."

    def register(self, dp: Dispatcher) -> None:
        router = Router(name="plugin_ping")

        async def _handler(message: Message) -> None:
            if not await is_message_from_owner(message):
                return
            start = time.monotonic()
            msg = await message.reply("🏓 Понг...")
            elapsed_ms = (time.monotonic() - start) * 1000
            await msg.edit_text(f"🏓 Понг! {elapsed_ms:.0f} мс")

        pattern = r"(?i)^/ping"
        router.message.register(_handler, F.text.regexp(pattern))
        router.business_message.register(_handler, F.text.regexp(pattern))
        dp.include_router(router)
