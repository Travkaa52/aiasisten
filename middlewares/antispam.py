import re
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from aiogram.exceptions import TelegramBadRequest
from database import get_spam_filters
from config import OWNER_ID

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)\S+",
    re.IGNORECASE
)


class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if not event.text:
            return await handler(event, data)

        user = event.from_user
        if not user or user.id == OWNER_ID:
            return await handler(event, data)

        if not event.chat or event.chat.type == "private":
            return await handler(event, data)

        filters = await get_spam_filters()
        text_lower = event.text.lower()

        for f in filters:
            if f["filter_type"] == "links":
                if URL_PATTERN.search(event.text):
                    try:
                        await event.delete()
                        await event.answer(
                            f"⚠️ {user.first_name}, ссылки запрещены в этом чате!"
                        )
                    except TelegramBadRequest:
                        pass
                    return

            elif f["filter_type"] == "words":
                if f["value"].lower() in text_lower:
                    try:
                        await event.delete()
                        await event.answer(
                            f"⚠️ {user.first_name}, вы использовали запрещённое слово!"
                        )
                    except TelegramBadRequest:
                        pass
                    return

        return await handler(event, data)
