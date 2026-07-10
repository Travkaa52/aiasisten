"""
main.py
Точка входа приложения.

Логика запуска рассчитана на выполнение внутри GitHub Actions job,
который сам по себе живёт ограниченное время и перезапускается по cron
каждые 5 минут:
  1. инициализируем логирование и БД;
  2. подключаемся к Telegram Bot API (aiogram) по BOT_TOKEN — бот заранее
     подключён владельцем к его аккаунту через функцию Telegram Business
     «Чат-боты» (Settings → Telegram Business → Чат-боты), это НЕ Telethon
     и не требует api_id/api_hash;
  3. регистрируем все обработчики (business connection, команды,
     автоответчик, медиа, плагины) и запускаем планировщик;
  4. слушаем события (long polling) ровно run_duration_seconds, затем
     аккуратно останавливаем планировщик, закрываем сессию бота и
     выходим с кодом 0;
  5. любая необработанная ошибка -> логируется и процесс завершается
     с кодом 1, чтобы GitHub Actions явно показал failed job.
"""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from assistant.ai import ai_client
from assistant.config import config
from assistant.database import dispose_engine, init_db
from assistant.handlers.autoresponder import register_autoresponder
from assistant.handlers.business import register_business_handlers
from assistant.handlers.commands import register_command_handlers
from assistant.handlers.media import register_media_handlers
from assistant.handlers.plugins_handler import register_plugins
from assistant.logger import log
from assistant.scheduler import TaskScheduler

# business_connection / business_message / edited_business_message /
# deleted_business_messages — обновления функции Telegram Business
# «Чат-боты» (Automated messages). Без явного перечисления в allowed_updates
# Bot API их не пришлёт.
ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]


async def _connect_with_retry(bot: Bot) -> None:
    attempt = 0
    delay = config.reconnect_base_delay
    while True:
        attempt += 1
        try:
            me = await bot.get_me()
            log.info("Подключено к Telegram как @{} (id={}).", me.username, me.id)
            return
        except Exception as exc:  # noqa: BLE001
            if attempt >= config.reconnect_max_attempts:
                log.error("Не удалось подключиться к Telegram Bot API после {} попыток.", attempt)
                raise
            log.warning(
                "Попытка подключения {}/{} не удалась: {}. Повтор через {:.1f}с.",
                attempt,
                config.reconnect_max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= 2


async def run() -> int:
    log.info("=== AI Assistant запускается ===")
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties())

    try:
        await _connect_with_retry(bot)
    except Exception as exc:  # noqa: BLE001
        log.exception("Критическая ошибка подключения: {}", exc)
        await bot.session.close()
        return 1

    dp = Dispatcher()

    # Порядок важен: business_connection — служебные апдейты без текста;
    # commands/media обрабатывают только сообщения владельца (self-команды);
    # autoresponder — фоллбек для всех остальных (клиентских) сообщений.
    register_business_handlers(dp)
    register_command_handlers(dp)
    register_media_handlers(dp)
    register_autoresponder(dp)
    register_plugins(dp)

    scheduler = TaskScheduler(bot)
    scheduler.start()

    exit_code = 0
    try:
        log.info(
            "Ассистент активен, слушаю события {} секунд...", config.run_duration_seconds
        )
        await asyncio.wait_for(
            dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES, handle_signals=False),
            timeout=config.run_duration_seconds,
        )
    except asyncio.TimeoutError:
        log.info("Истекло время работы job'а ({}с) — штатное завершение.", config.run_duration_seconds)
    except Exception as exc:  # noqa: BLE001
        log.exception("Необработанная ошибка во время работы: {}", exc)
        exit_code = 1
    finally:
        scheduler.shutdown()
        try:
            await dp.stop_polling()
        except Exception as exc:  # noqa: BLE001
            log.debug("stop_polling: {}", exc)
        try:
            await bot.session.close()
        except Exception as exc:  # noqa: BLE001
            log.error("Ошибка при закрытии сессии бота: {}", exc)
        await ai_client.close()
        await dispose_engine()
        log.info("=== AI Assistant завершил работу (код {}) ===", exit_code)

    return exit_code


def main() -> None:
    try:
        exit_code = asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Остановлено пользователем (KeyboardInterrupt).")
        exit_code = 0
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001
        log.exception("Фатальная ошибка на верхнем уровне: {}", exc)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
