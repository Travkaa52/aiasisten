import asyncio
import logging
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, LOG_LEVEL
from database.database import init_db
from middlewares.auth import AuthMiddleware
from middlewares.antispam import AntiSpamMiddleware
from handlers import admin, users, support


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ]
    )


async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Business AI Assistant Bot...")

    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        return

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middlewares для обычных сообщений (ЛС бота)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(AntiSpamMiddleware())
    dp.callback_query.middleware(AntiSpamMiddleware())

    # Middlewares для Business Mode (личные чаты бизнес-аккаунта)
    dp.business_message.middleware(AuthMiddleware())
    dp.business_message.middleware(AntiSpamMiddleware())

    # Роутеры
    dp.include_router(admin.router)
    dp.include_router(support.router)
    dp.include_router(users.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is running in Business Mode with Gemini AI. Press Ctrl+C to stop.")

    # Корректно обрабатываем SIGTERM (например, от `timeout` в CI/systemd/Docker),
    # чтобы поллинг всегда завершался штатно, а не убивался жёстко.
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_stop_signal(sig_name: str):
        logger.info(f"Получен сигнал {sig_name}, начинаю штатную остановку...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_stop_signal, sig.name)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler
            pass

    async def _watch_stop_event():
        await stop_event.wait()
        await dp.stop_polling()

    watcher_task = asyncio.create_task(_watch_stop_event())

    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "business_message",
                "edited_business_message",
            ]
        )
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        watcher_task.cancel()
        logger.info("Closing bot session...")
        await bot.session.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped by user.")
