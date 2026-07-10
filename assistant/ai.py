"""
ai.py
Обёртка над Anthropic Messages API (текст + vision) и OpenAI API
(генерация изображений, Whisper transcription). Всё полностью асинхронно
через aiohttp, без блокирующих SDK-клиентов.

Если соответствующий API-ключ не задан, функция явно логирует
предупреждение и возвращает понятную ошибку пользователю — никаких
тихих заглушек или фейковых ответов.
"""

from __future__ import annotations

import base64
from typing import Any

import aiohttp

from assistant.config import config
from assistant.logger import log

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_AUDIO_URL = "https://api.openai.com/v1/audio/transcriptions"

ANTHROPIC_VERSION = "2023-06-01"


class AIError(RuntimeError):
    """Ошибка при обращении к внешнему AI API."""


class AIClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Anthropic text / vision
    # ------------------------------------------------------------------
    async def _anthropic_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not config.anthropic_api_key:
            raise AIError(
                "ANTHROPIC_API_KEY не задан — текстовые AI-функции отключены. "
                "Добавьте ключ в GitHub Secrets / .env."
            )
        session = await self._get_http_session()
        headers = {
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            async with session.post(ANTHROPIC_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    err = data.get("error", {}).get("message", str(data))
                    log.error("Anthropic API вернул ошибку {}: {}", resp.status, err)
                    raise AIError(f"AI API ошибка ({resp.status}): {err}")
                return data
        except aiohttp.ClientError as exc:
            log.error("Сетевая ошибка при запросе к Anthropic API: {}", exc)
            raise AIError(f"Сетевая ошибка AI API: {exc}") from exc

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        parts = data.get("content", [])
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(t for t in texts if t).strip()

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Обычный диалоговый ответ с учётом контекста памяти."""
        payload: dict[str, Any] = {
            "model": config.anthropic_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        data = await self._anthropic_request(payload)
        return self._extract_text(data)

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

    async def ocr_image(self, image_bytes: bytes, media_type: str = "image/jpeg") -> str:
        """Распознавание текста на изображении через vision-модель Claude."""
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": config.anthropic_model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Извлеки весь текст, видимый на изображении, дословно. "
                                "Если текста нет — кратко опиши, что изображено."
                            ),
                        },
                    ],
                }
            ],
        }
        data = await self._anthropic_request(payload)
        return self._extract_text(data)

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
    # OpenAI: генерация изображений
    # ------------------------------------------------------------------
    async def generate_image(self, prompt: str) -> str:
        """Возвращает URL сгенерированного изображения."""
        if not config.openai_api_key:
            raise AIError(
                "OPENAI_API_KEY не задан — генерация изображений отключена. "
                "Добавьте ключ в GitHub Secrets / .env."
            )
        session = await self._get_http_session()
        headers = {
            "Authorization": f"Bearer {config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.openai_image_model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }
        try:
            async with session.post(OPENAI_IMAGES_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    err = data.get("error", {}).get("message", str(data))
                    log.error("OpenAI Images API ошибка {}: {}", resp.status, err)
                    raise AIError(f"Ошибка генерации изображения ({resp.status}): {err}")
                return data["data"][0]["url"]
        except aiohttp.ClientError as exc:
            log.error("Сетевая ошибка при запросе к OpenAI Images API: {}", exc)
            raise AIError(f"Сетевая ошибка при генерации изображения: {exc}") from exc

    # ------------------------------------------------------------------
    # OpenAI: Voice-to-Text (Whisper)
    # ------------------------------------------------------------------
    async def transcribe_voice(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        if not config.openai_api_key:
            raise AIError(
                "OPENAI_API_KEY не задан — распознавание голоса отключено. "
                "Добавьте ключ в GitHub Secrets / .env."
            )
        session = await self._get_http_session()
        headers = {"Authorization": f"Bearer {config.openai_api_key}"}
        form = aiohttp.FormData()
        form.add_field("model", config.openai_whisper_model)
        form.add_field(
            "file", audio_bytes, filename=filename, content_type="application/octet-stream"
        )
        try:
            async with session.post(OPENAI_AUDIO_URL, data=form, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    err = data.get("error", {}).get("message", str(data))
                    log.error("OpenAI Whisper API ошибка {}: {}", resp.status, err)
                    raise AIError(f"Ошибка распознавания голоса ({resp.status}): {err}")
                return data.get("text", "").strip()
        except aiohttp.ClientError as exc:
            log.error("Сетевая ошибка при запросе к OpenAI Whisper API: {}", exc)
            raise AIError(f"Сетевая ошибка при распознавании голоса: {exc}") from exc


ai_client = AIClient()
