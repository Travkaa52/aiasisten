"""
handlers/media.py
Обработка входящих медиа от владельца (self-commands через reply на медиа
или прямая отправка себе):
  - фото + подпись "/ocr" -> распознавание текста
  - голосовое + "/voice" -> транскрибация в текст
  - документ + "/analyze" -> анализ содержимого файла
  - "/imagine <промпт>" -> генерация изображения
"""

from __future__ import annotations

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from assistant.ai import AIError, ai_client
from assistant.logger import log
from assistant.utils.file_utils import cleanup_tmp, new_tmp_path, read_text_file
from assistant.utils.text_utils import is_command, strip_command

TEXT_LIKE_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".log", ".ini", ".cfg",
}


async def handle_ocr(event: events.NewMessage.Event) -> None:
    target: Message | None = event.message
    if not target.photo and target.is_reply:
        target = await target.get_reply_message()
    if target is None or not target.photo:
        await event.reply("⚠️ Прикрепите или ответьте на фото с командой /ocr.")
        return

    status = await event.reply("🔍 Распознаю текст на изображении...")
    tmp_path = new_tmp_path(".jpg")
    try:
        await target.download_media(file=str(tmp_path))
        image_bytes = tmp_path.read_bytes()
        text = await ai_client.ocr_image(image_bytes)
        result = text if text else "Текст на изображении не найден."
        await status.edit(f"📄 Результат OCR:\n\n{result}")
    except AIError as exc:
        await status.edit(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка OCR: {}", exc)
        await status.edit("❌ Не удалось обработать изображение.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_voice(event: events.NewMessage.Event) -> None:
    target: Message | None = event.message
    if not (target.voice or target.audio) and target.is_reply:
        target = await target.get_reply_message()
    if target is None or not (target.voice or target.audio):
        await event.reply("⚠️ Прикрепите или ответьте на голосовое с командой /voice.")
        return

    status = await event.reply("🎙️ Распознаю голосовое сообщение...")
    tmp_path = new_tmp_path(".ogg")
    try:
        await target.download_media(file=str(tmp_path))
        audio_bytes = tmp_path.read_bytes()
        text = await ai_client.transcribe_voice(audio_bytes, filename=tmp_path.name)
        result = text if text else "Не удалось распознать речь."
        await status.edit(f"📝 Расшифровка:\n\n{result}")
    except AIError as exc:
        await status.edit(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка транскрибации: {}", exc)
        await status.edit("❌ Не удалось обработать голосовое сообщение.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_analyze_file(event: events.NewMessage.Event) -> None:
    target: Message | None = event.message
    if not target.document and target.is_reply:
        target = await target.get_reply_message()
    if target is None or not target.document:
        await event.reply("⚠️ Прикрепите или ответьте на файл с командой /analyze.")
        return

    filename = "file"
    for attr in target.document.attributes:
        if hasattr(attr, "file_name") and attr.file_name:
            filename = attr.file_name
            break

    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    status = await event.reply(f"📎 Анализирую файл {filename}...")
    tmp_path = new_tmp_path(suffix)
    try:
        await target.download_media(file=str(tmp_path))

        if suffix in TEXT_LIKE_EXTENSIONS:
            content = await read_text_file(tmp_path)
            analysis = await ai_client.analyze_file_text(filename, content)
            await status.edit(f"📎 Анализ файла {filename}:\n\n{analysis}")
        else:
            size_kb = tmp_path.stat().st_size / 1024
            await status.edit(
                f"📎 Файл {filename} ({size_kb:.1f} KB).\n"
                "Автоматический текстовый анализ поддерживается только для "
                f"текстовых форматов: {', '.join(sorted(TEXT_LIKE_EXTENSIONS))}."
            )
    except AIError as exc:
        await status.edit(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка анализа файла: {}", exc)
        await status.edit("❌ Не удалось обработать файл.")
    finally:
        await cleanup_tmp(tmp_path)


async def handle_imagine(event: events.NewMessage.Event) -> None:
    prompt = strip_command(event.raw_text)
    if not prompt:
        await event.reply("⚠️ Использование: /imagine <описание изображения>")
        return

    status = await event.reply("🎨 Генерирую изображение...")
    try:
        url = await ai_client.generate_image(prompt)
        await status.delete()
        await event.reply(f"🎨 Готово!\n{url}")
    except AIError as exc:
        await status.edit(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("Ошибка генерации изображения: {}", exc)
        await status.edit("❌ Не удалось сгенерировать изображение.")


def register_media_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/ocr"))
    async def _ocr(event: events.NewMessage.Event) -> None:
        await handle_ocr(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/voice"))
    async def _voice(event: events.NewMessage.Event) -> None:
        await handle_voice(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/analyze"))
    async def _analyze(event: events.NewMessage.Event) -> None:
        await handle_analyze_file(event)

    @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/imagine"))
    async def _imagine(event: events.NewMessage.Event) -> None:
        await handle_imagine(event)
