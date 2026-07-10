"""
main.py
Точка входа приложения.

Логика запуска рассчитана на выполнение внутри GitHub Actions job,
который сам по себе живёт ограниченное время и перезапускается по cron
каждые 5 минут:
  1. инициализируем логирование и БД;
  2. подключаемся к Telegram через Telethon (StringSession, user-аккаунт)
     с ретраями и экспоненциальной задержкой при сбое сети;
  3. регистрируем все обработчики (команды, автоответчик, антиспам,
     медиа, плагины) и запускаем планировщик;
  4. слушаем события ровно run_duration_seconds, затем аккуратно
     останавливаем планировщик, отключаемся и выходим с кодом 0;
  5. любая необработанная ошибка -> логируется и процесс завершается
     с кодом 1, чтобы GitHub Actions явно показал failed job.
"""

from __future__ import annotations

import asyncio
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import AuthKeyError, FloodWaitError

from assistant.ai import ai_client
from assistant.config import config
from assistant.database import dispose_engine, init_db
from assistant.handlers.autoresponder import register_autoresponder
from assistant.handlers.commands import register_command_handlers
from assistant.handlers.media import register_media_handlers
from assistant.handlers.plugins_handler import register_plugins
from assistant.logger import log
from assistant.scheduler import TaskScheduler


async def _connect_with_retry(client: TelegramClient) -> None:
    attempt = 0
    delay = config.reconnect_base_delay
    while True:
        attempt += 1
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise AuthKeyError(
                    "SESSION невалидна или истекла. Сгенерируйте новую StringSession "
                    "и обновите GitHub Secret 'SESSION'."
                )
            me = await client.get_me()
            log.info("Подключено к Telegram как {} (id={}).", me.username or me.first_name, me.id)
            return
        except AuthKeyError:
            raise  # невалидная сессия — ретраи бессмысленны, падаем сразу
        except FloodWaitError as exc:
            log.warning("FloodWait: нужно подождать {} секунд.", exc.seconds)
            await asyncio.sleep(exc.seconds)
        except Exception as exc:  # noqa: BLE001
            if attempt >= config.reconnect_max_attempts:
                log.error("Не удалось подключиться к Telegram после {} попыток.", attempt)
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

    client = TelegramClient(
        StringSession(config.session_string),
        config.api_id,
        config.api_hash,
        connection_retries=5,
        auto_reconnect=True,
        retry_delay=2,
    )

    try:
        await _connect_with_retry(client)
    except Exception as exc:  # noqa: BLE001
        log.exception("Критическая ошибка подключения: {}", exc)
        return 1

    register_command_handlers(client)
    register_media_handlers(client)
    register_autoresponder(client)
    register_plugins(client)

    scheduler = TaskScheduler(client)
    scheduler.start()

    exit_code = 0
    try:
        log.info(
            "Ассистент активен, слушаю события {} секунд...", config.run_duration_seconds
        )
        await asyncio.wait_for(
            client.run_until_disconnected(), timeout=config.run_duration_seconds
        )
    except asyncio.TimeoutError:
        log.info("Истекло время работы job'а ({}с) — штатное завершение.", config.run_duration_seconds)
    except Exception as exc:  # noqa: BLE001
        log.exception("Необработанная ошибка во время работы: {}", exc)
        exit_code = 1
    finally:
        scheduler.shutdown()
        try:
            await client.disconnect()
        except Exception as exc:  # noqa: BLE001
            log.error("Ошибка при отключении от Telegram: {}", exc)
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
