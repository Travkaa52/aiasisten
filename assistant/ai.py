"""
ai.py
Обёртка над Google Gemini API (google-genai SDK): текстовый диалог,
vision (OCR по фото), понимание аудио (voice-to-text) и генерация
изображений — всё одним провайдером вместо Anthropic+OpenAI.

Если GEMINI_API_KEY не задан, функция явно логирует предупреждение и
возвращает понятную ошибку пользователю — никаких тихих заглушек или
фейковых ответов.
"""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from assistant.config import config
from assistant.logger import log


class AIError(RuntimeError):
    """Ошибка при обращении к внешнему AI API (Gemini)."""


# Роли в истории памяти у нас "user" / "assistant", а Gemini ожидает
# "user" / "model" — конвертируем при сборке contents.
_ROLE_MAP = {"user": "user", "assistant": "model"}


class AIClient:
    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not config.gemini_api_key:
            raise AIError(
                "GEMINI_API_KEY не задан — AI-функции отключены. "
                "Получите ключ в Google AI Studio (aistudio.google.com/apikey) "
                "и добавьте его в GitHub Secrets / .env."
            )
        if self._client is None:
            self._client = genai.Client(api_key=config.gemini_api_key)
        return self._client

    async def close(self) -> None:
        # У google-genai нет отдельного метода закрытия HTTP-сессии,
        # оставлено для симметрии с остальным кодом (main.py вызывает
        # ai_client.close() при завершении работы).
        return None

    @staticmethod
    def _extract_text(response: Any) -> str:
        text = getattr(response, "text", None)
        return (text or "").strip()

    # ------------------------------------------------------------------
    # Текстовый диалог
    # ------------------------------------------------------------------
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Обычный диалоговый ответ с учётом контекста памяти."""
        client = self._get_client()
        contents = [
            types.Content(
                role=_ROLE_MAP.get(m["role"], "user"),
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        gen_config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        )
        try:
            response = await client.aio.models.generate_content(
                model=config.gemini_model, contents=contents, config=gen_config
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Gemini API вернул ошибку: {}", exc)
            raise AIError(f"AI API ошибка: {exc}") from exc
        return self._extract_text(response)

    async def rewrite(self, text: str, style: str = "более вежливо и профессионально") -> str:
        system = (
            "Ты — редактор текста. Перепиши сообщение пользователя так, как он просит, "
            "сохранив исходный смысл. Верни только переписанный текст, без пояснений."
        )
        prompt = f"Стиль перезаписи: {style}.\n\nТекст:\n{text}"
        return await self.chat([{"role": "user", "content": prompt}], system=system, max_tokens=1024)

    async def translate(self, text: str, target_lang: str = "английский") -> str:
        system = (
            "Ты — профессиональный переводчик. Переведи текст пользователя на указанный "
            "язык. Верни только перевод, без пояснений и кавычек."
        )
        prompt = f"Целевой язык: {target_lang}.\n\nТекст:\n{text}"
        return await self.chat([{"role": "user", "content": prompt}], system=system, max_tokens=1024)

    async def summarize(self, text: str, max_sentences: int = 5) -> str:
        system = (
            "Ты — ассистент для суммаризации. Сделай краткое, но информативное "
            f"саммари текста максимум в {max_sentences} предложений. Ответь на языке "
            "оригинального текста."
        )
        return await self.chat([{"role": "user", "content": text}], system=system, max_tokens=512)

    async def analyze_file_text(self, filename: str, content: str) -> str:
        """Анализ содержимого текстового файла: краткое описание/выводы."""
        system = (
            "Ты — ассистент для анализа файлов. Опиши содержимое файла кратко: "
            "тип содержимого, ключевые моменты, потенциальные проблемы (если это код "
            "или конфигурация)."
        )
        prompt = f"Файл: {filename}\n\nСодержимое:\n{content[:8000]}"
        return await self.chat([{"role": "user", "content": prompt}], system=system, max_tokens=800)

    # ------------------------------------------------------------------
    # Vision: OCR по изображению
    # ------------------------------------------------------------------
    async def ocr_image(self, image_bytes: bytes, media_type: str = "image/jpeg") -> str:
        """Распознавание текста на изображении через vision-модель Gemini."""
        client = self._get_client()
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                    types.Part.from_text(
                        text=(
                            "Извлеки весь текст, видимый на изображении, дословно. "
                            "Если текста нет — кратко опиши, что изображено."
                        )
                    ),
                ],
            )
        ]
        try:
            response = await client.aio.models.generate_content(
                model=config.gemini_model, contents=contents
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Gemini API (OCR) вернул ошибку: {}", exc)
            raise AIError(f"AI API ошибка ({exc}).") from exc
        return self._extract_text(response)

    # ------------------------------------------------------------------
    # Audio understanding: Voice-to-Text
    # ------------------------------------------------------------------
    async def transcribe_voice(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Расшифровка голосового сообщения. Gemini понимает аудио нативно —
        отдельный сервис (Whisper) больше не нужен."""
        client = self._get_client()
        mime_type = "audio/ogg" if filename.lower().endswith(".ogg") else "audio/mpeg"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    types.Part.from_text(
                        text="Расшифруй речь из аудио дословно, без пояснений и комментариев."
                    ),
                ],
            )
        ]
        try:
            response = await client.aio.models.generate_content(
                model=config.gemini_model, contents=contents
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Gemini API (аудио) вернул ошибку: {}", exc)
            raise AIError(f"AI API ошибка ({exc}).") from exc
        return self._extract_text(response)

    # ------------------------------------------------------------------
    # Генерация изображений
    # ------------------------------------------------------------------
    async def generate_image(self, prompt: str) -> bytes:
        """Возвращает сырые байты сгенерированного изображения (PNG).

        В отличие от OpenAI Images API, Gemini не отдаёт готовый URL —
        изображение приходит как inline-данные в ответе, поэтому вызывающий
        код (handlers/media.py) отправляет их в Telegram напрямую как файл.
        """
        client = self._get_client()
        try:
            response = await client.aio.models.generate_content(
                model=config.gemini_image_model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Gemini Image API ошибка: {}", exc)
            raise AIError(f"Ошибка генерации изображения: {exc}") from exc

        for candidate in getattr(response, "candidates", []) or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and inline.data:
                    return inline.data

        raise AIError("Gemini не вернул изображение в ответе — попробуйте переформулировать промпт.")


ai_client = AIClient()
