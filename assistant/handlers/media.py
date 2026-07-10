"""
handlers/media.py
Обработка входящих медиа от владельца (self-commands в ответ на медиа,
или прямая отправка себе):
  - фото + подпись "/ocr" -> распознавание текста
  - голосовое + "/voice" -> транскрибация в текст (нативно через Gemini)
  - документ + "/analyze" -> анализ содержимого файла
  - "/imagine <промпт>" -> генерация изображения (Gemini)
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter
from aiogram.types import BufferedInputFile, Message

from assistant.ai import AIError, ai_client
from assistant.handlers.access import is_message_from_owner
from assistant.logger import log
from assistant.utils.file_utils import cleanup_tmp, new_tmp_path, read_text_file
from assistant.utils.text_utils import strip_command

router = Router(name="media")

TEXT_LIKE_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".log", ".ini", ".cfg",
}


class IsOwner(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return await is_message_from_owner(message)


def _register(pattern: str, handler) -> None:
    text_filter = F.text.regexp(pattern) | F.caption.regexp(pattern)
    router.message.register(handler, IsOwner(), text_filter)
    router.business_message.register(handler, IsOwner(), text_filter)


async def _resolve_target(message: Message, attr: str) -> Message | None:
    """Возвращает сообщение, содержащее нужный тип медиа: само сообщение
    (если команда была подписью к медиа) либо сообщение, на которое
    ответили командой."""
    if getattr(message, attr, None):
        return message
    if message.reply_to_message and getattr(message.reply_to_message, attr, None):
        return message.reply_to_message
    return None


async def handle_ocr(message: Message, bot: Bot) -> None:
    target = await _resolve_target(message, "photo")
    if target is None:
        await message.reply("⚠️ Прикрепите или ответьте на фото с командой /ocr.")
        return

    status = await message.reply("🔍 Распознаю текст на изображении...")
    tmp_path = new_tmp_path(".jpg")
    try:
        photo = target.photo[-1]
        await bot.download(photo.file_id, destination=str(tmp_path))
        image_bytes = tmp_path.read_bytes()
        text = await ai_client.ocr_image(image_bytes)
        result = text if text else "Текст на изображении не найден."
        await status.edit_text(f"📄 Результат OCR:\n\n{result}")
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка OCR: {}", exc)
        await status.edit_text("❌ Не удалось обработать изображение.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_voice(message: Message, bot: Bot) -> None:
    target = await _resolve_target(message, "voice")
    if target is None:
        target = await _resolve_target(message, "audio")
    if target is None:
        await message.reply("⚠️ Прикрепите или ответьте на голосовое с командой /voice.")
        return

    status = await message.reply("🎙️ Распознаю голосовое сообщение...")
    media = target.voice or target.audio
    tmp_path = new_tmp_path(".ogg")
    try:
        await bot.download(media.file_id, destination=str(tmp_path))
        audio_bytes = tmp_path.read_bytes()
        text = await ai_client.transcribe_voice(audio_bytes, filename=tmp_path.name)
        result = text if text else "Не удалось распознать речь."
        await status.edit_text(f"📝 Расшифровка:\n\n{result}")
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка транскрибации: {}", exc)
        await status.edit_text("❌ Не удалось обработать голосовое сообщение.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_analyze_file(message: Message, bot: Bot) -> None:
    target = await _resolve_target(message, "document")
    if target is None:
        await message.reply("⚠️ Прикрепите или ответьте на файл с командой /analyze.")
        return

    document = target.document
    filename = document.file_name or "file"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    status = await message.reply(f"📎 Анализирую файл {filename}...")
    tmp_path = new_tmp_path(suffix)
    try:
        await bot.download(document.file_id, destination=str(tmp_path))

        if suffix in TEXT_LIKE_EXTENSIONS:
            content = await read_text_file(tmp_path)
            analysis = await ai_client.analyze_file_text(filename, content)
            await status.edit_text(f"📎 Анализ файла {filename}:\n\n{analysis}")
        else:
            size_kb = tmp_path.stat().st_size / 1024
            await status.edit_text(
                f"📎 Файл {filename} ({size_kb:.1f} KB).\n"
                "Автоматический текстовый анализ поддерживается только для "
                f"текстовых форматов: {', '.join(sorted(TEXT_LIKE_EXTENSIONS))}."
            )
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка анализа файла: {}", exc)
        await status.edit_text("❌ Не удалось обработать файл.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_imagine(message: Message) -> None:
    prompt = strip_command(message.text or message.caption or "")
    if not prompt:
        await message.reply("⚠️ Использование: /imagine <описание изображения>")
        return

    status = await message.reply("🎨 Генерирую изображение...")
    try:
        image_bytes = await ai_client.generate_image(prompt)
        photo = BufferedInputFile(image_bytes, filename="imagine.png")
        await status.delete()
        await message.reply_photo(photo, caption="🎨 Готово!")
    except AIError as exc:
        await status.edit_text(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка генерации изображения: {}", exc)
        await status.edit_text("❌ Не удалось сгенерировать изображение.")


_register(r"(?i)^/ocr", handle_ocr)
_register(r"(?i)^/voice", handle_voice)
_register(r"(?i)^/analyze", handle_analyze_file)


async def _imagine_handler(message: Message) -> None:
    await handle_imagine(message)


_register(r"(?i)^/imagine", _imagine_handler)


def register_media_handlers(dp) -> None:
    dp.include_router(router)
    log.info("Обработчики медиа зарегистрированы.")
