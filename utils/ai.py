import logging
import asyncio
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from config import (
    GEMINI_KEY, GEMINI_MODEL, GEMINI_MODEL_FALLBACK,
    OWNER_NAME, BUSINESS_NAME, BUSINESS_DESCRIPTION,
    AI_LANGUAGE, AI_HISTORY_DEPTH
)
from database.database import (
    get_ai_settings, add_to_history, get_history, get_contact_note
)

logger = logging.getLogger(__name__)

if GEMINI_KEY and GEMINI_KEY.strip():
    _client = genai.Client(api_key=GEMINI_KEY)
    logger.info(f"Gemini API client initialized. Primary model: {GEMINI_MODEL}, fallback: {GEMINI_MODEL_FALLBACK}.")
else:
    _client = None
    logger.warning("GEMINI_KEY is empty! AI replies will be disabled.")


async def _generate_with_fallback(contents, config: "types.GenerateContentConfig"):
    """
    Пытается сгенерировать ответ основной моделью (GEMINI_MODEL).
    Если она недоступна (лимиты, регион, модель устарела/выключена) —
    автоматически переключается на резервную модель (GEMINI_MODEL_FALLBACK).
    """
    models_to_try = [GEMINI_MODEL]
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL:
        models_to_try.append(GEMINI_MODEL_FALLBACK)

    last_error = None
    for idx, model_name in enumerate(models_to_try):
        try:
            response = await asyncio.to_thread(
                _client.models.generate_content,
                model=model_name,
                contents=contents,
                config=config,
            )
            if idx > 0:
                logger.warning(f"AI: основная модель недоступна, использована резервная модель '{model_name}'.")
            return response
        except genai_errors.APIError as e:
            last_error = e
            logger.warning(f"Gemini model '{model_name}' failed ({e}). Trying next fallback if available.")
        except Exception as e:
            last_error = e
            logger.warning(f"Gemini model '{model_name}' failed with unexpected error ({e}).")

    if last_error:
        raise last_error
    raise RuntimeError("Не удалось получить ответ ни от одной из моделей Gemini.")


def _build_system_prompt(settings: dict, contact_note: str = "") -> str:
    """Формирует системный промпт с учётом настроек из БД и заметки о контакте."""
    custom = (settings.get("system_prompt") or "").strip()

    base = f"""Ты — персональный ИИ-ассистент {OWNER_NAME} в Telegram Business Mode.
Ты отвечаешь ОТ ИМЕНИ {OWNER_NAME} в его личных переписках с клиентами и партнёрами.

О бизнесе:
{BUSINESS_DESCRIPTION}
Название компании / бренд: {BUSINESS_NAME}

Правила поведения:
1. Отвечай кратко, по делу, в деловом но дружелюбном стиле.
2. Язык ответов: {AI_LANGUAGE}. Переключайся на язык собеседника если он пишет на другом.
3. НЕ раскрывай, что ты ИИ, если тебя об этом прямо не спросят.
4. Если вопрос требует личного ответа {OWNER_NAME} (встречи, договора, цены), скажи что {OWNER_NAME} свяжется чуть позже.
5. Не обещай то, чего не знаешь точно.
6. Будь вежлив, профессионален, не используй грубую лексику.
7. Если не знаешь ответ — честно скажи это и предложи уточнить у {OWNER_NAME}.
"""
    if contact_note:
        base += f"\nДополнительная информация об этом контакте (для тебя, не озвучивай):\n{contact_note}\n"

    if custom:
        base += f"\nДополнительные инструкции от владельца:\n{custom}"

    return base


async def generate_ai_reply(
    user_text: str,
    chat_id: int = None,
    user_name: str = ""
) -> str:
    """
    Генерирует ответ Gemini с учётом истории диалога.
    chat_id — идентификатор чата для сохранения истории.
    """
    if not _client:
        logger.warning("Gemini client is not initialized. Skipping AI generation.")
        return ""

    try:
        settings = await get_ai_settings()

        # Проверяем режим
        mode = settings.get("mode", "smart")
        if mode == "off":
            return ""

        # Заметка о контакте
        note = ""
        if chat_id:
            note = await get_contact_note(chat_id)

        system_prompt = _build_system_prompt(settings, note)

        # История диалога
        history = []
        if chat_id:
            history = await get_history(chat_id, limit=AI_HISTORY_DEPTH)

        # Формируем контент для Gemini
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        # Добавляем новое сообщение
        user_content = user_text
        if user_name:
            user_content = f"[{user_name}]: {user_text}"
        contents.append(types.Content(role="user", parts=[types.Part(text=user_content)]))

        response = await _generate_with_fallback(
            contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=800,
                temperature=0.75,
            )
        )

        reply_text = response.text.strip() if response.text else ""

        # Сохраняем в историю
        if chat_id and reply_text:
            await add_to_history(chat_id, "user", user_text)
            await add_to_history(chat_id, "model", reply_text)

        return reply_text

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return ""


async def generate_custom_response(prompt: str, system: str = "") -> str:
    """Быстрая генерация без истории — для внутренних нужд бота."""
    if not _client:
        return ""
    try:
        cfg = types.GenerateContentConfig(max_output_tokens=800, temperature=0.6)
        if system:
            cfg = types.GenerateContentConfig(
                system_instruction=system, max_output_tokens=800, temperature=0.6
            )
        response = await _generate_with_fallback(prompt, config=cfg)
        return response.text.strip() if response.text else ""
    except Exception as e:
        logger.error(f"Gemini custom response error: {e}")
        return ""
