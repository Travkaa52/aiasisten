"""
plugins/ping_plugin.py
Пример полностью рабочего плагина: команда /ping измеряет задержку
между отправкой и редактированием сообщения (round-trip до Telegram).
"""

from __future__ import annotations

import time

from telethon import TelegramClient, events

from assistant.plugins.base import Plugin
from assistant.utils.text_utils import is_command


class PingPlugin(Plugin):
    name = "ping"
    description = "Проверка задержки ответа ассистента (/ping)."

    def register(self, client: TelegramClient) -> None:
        @client.on(events.NewMessage(outgoing=True))
        async def _handler(event: events.NewMessage.Event) -> None:
            if not is_command(event.raw_text, "ping"):
                return
            start = time.monotonic()
            msg = await event.reply("🏓 Понг...")
            elapsed_ms = (time.monotonic() - start) * 1000
            await msg.edit(f"🏓 Понг! {elapsed_ms:.0f} мс")
