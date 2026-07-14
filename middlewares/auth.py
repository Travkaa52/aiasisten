import logging
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database import add_user, is_banned, log_message
from config import OWNER_ID

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    def __init__(self, cache_ttl_seconds: int = 300):
        super().__init__()
        self.cache_ttl = cache_ttl_seconds
        self._user_reg_cache = {}
        self._ban_status_cache = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        # Проверяем, является ли апдейт бизнес-сообщением
        is_business = False
        if isinstance(event, Message) and event.business_connection_id:
            is_business = True

        user = event.from_user
        if not user:
            return await handler(event, data)

        # ЕСЛИ ЭТО ОБЫЧНЫЙ РЕЖИМ (Админ общается с ботом в его ЛС для настройки)
        if not is_business:
            current_time = time.time()
            # Синхронизация админа/менеджера в БД
            if current_time - self._user_reg_cache.get(user.id, 0.0) > self.cache_ttl:
                try:
                    await add_user(telegram_id=user.id, username=user.username or "", full_name=user.full_name or "")
                    self._user_reg_cache[user.id] = current_time
                except Exception as e:
                    logger.error(f"DB sync error: {e}")

            # Проверка глобального бана (только для интерфейса самого бота)
            if user.id != OWNER_ID:
                # Берем статус бана из кэша или БД
                banned = self._ban_status_cache.get(user.id, (None, 0))[0]
                if banned is None:
                    banned = await is_banned(user.id)
                    self._ban_status_cache[user.id] = (banned, current_time)
                
                if banned:
                    if isinstance(event, Message):
                        await event.answer("🚫 Вы заблокированы.")
                    return

        # ЕСЛИ ЭТО БИЗНЕС-РЕЖИМ (Клиент пишет вам в личку)
        else:
            # Здесь мы можем просто логировать входящие сообщения от клиентов для аналитики админ-панели
            if isinstance(event, Message):
                log_text = event.text or (f"[Caption] {event.caption}" if event.caption else f"[{event.content_type.upper()}]")
                try:
                    # Сохраняем историю сообщений клиента для графиков активности
                    await log_message(user.id, log_text[:500], "business_incoming")
                except Exception as e:
                    logger.error(f"Failed to log business message: {e}")

        return await handler(event, data)
