# Telegram AI Assistant

Production-ready персональный AI-ассистент для Telegram на **aiogram 3**
(обычный Bot API + функция **Telegram Business «Чат-боты»**, а не
Telethon-юзербот и не api_id/api_hash), с памятью диалога, автоответчиком,
плагинами и полным набором утилитарных функций. AI-провайдер — **Google
Gemini**. Работает как long-running процесс (Docker/self-host) либо как
короткоживущий job в **GitHub Actions**, запускаемый по расписанию каждые
5 минут.

## Как это работает

1. Вы создаёте обычного Telegram-бота через **@BotFather** и получаете
   `BOT_TOKEN`.
2. В настройках своего аккаунта: **Telegram → Настройки → Telegram
   Business → Чат-боты** (в английском интерфейсе — *Settings → Telegram
   Business → Chatbots*) — вы подключаете этого бота к своему личному
   аккаунту.
3. С этого момента Telegram присылает боту апдейт `business_connection`
   (кто подключил бота и с какими правами), а все входящие/исходящие
   сообщения в чатах вашего аккаунта дублируются боту как
   `business_message`.
4. Ассистент отличает:
   - сообщения **клиентов** (не вас) в этих чатах → отвечает через AI
     (автоответчик, с учётом истории диалога);
   - сообщения **от вас самих** (владельца) → это self-команды
     (`/rewrite`, `/remind`, `/note` и т.д.), как раньше в Telethon-версии,
     только теперь это работает без входа в аккаунт через api_id/api_hash.
5. Ответы отправляются через `bot.send_message(..., business_connection_id=...)`,
   поэтому получателю они видны как отправленные от вашего аккаунта, а не
   "от бота".

Никакой авторизации через `my.telegram.org`, `StringSession` или номер
телефона не требуется — только обычный токен бота.

## Возможности

| Категория | Что делает |
|---|---|
| AI Assistant | Диалог с учётом контекста памяти (`memory.py`) через Google Gemini |
| Автоответы | Автоматически отвечает клиентам в бизнес-чатах и личных сообщениях (`handlers/autoresponder.py`) |
| Переписывание | `/rewrite <стиль>` в ответ на сообщение |
| Перевод | `/translate <язык>` в ответ на сообщение |
| Суммаризация | `/summarize` в ответ на сообщение |
| Напоминания | `/remind`, `/reminders`, `/unremind` — доставка через APScheduler |
| Заметки | `/note add|list|get|del` |
| Поиск | `/search <запрос>` по истории сообщений |
| OCR | `/ocr` в ответ на фото (через Gemini vision) |
| Voice-to-Text | `/voice` в ответ на голосовое (нативно через Gemini, без Whisper) |
| Генерация изображений | `/imagine <промпт>` (через Gemini image generation) |
| Анализ файлов | `/analyze` в ответ на документ |
| Плагины | Автозагрузка из `assistant/plugins/` |
| Статистика | `/stats` |
| Антиспам | Sliding-window rate limit + авто-блэклист |
| Whitelist/Blacklist | `/whitelist`, `/blacklist` |
| Do Not Disturb | `/dnd on|off|status` |

Self-команды пишутся **в чатах вашего аккаунта, подключённого через
функцию «Чат-боты»** (или просто напрямую боту в личных сообщениях, если
вы в `OWNER_IDS`) — например, ответом на сообщение клиента.

## Архитектура

```
assistant/
    main.py               # точка входа: aiogram polling, run/shutdown
    config.py              # конфигурация из .env / переменных окружения
    database.py             # async SQLAlchemy engine + сессии (SQLite)
    logger.py                # loguru: консоль + ротируемые файлы
    ai.py                     # Google Gemini: чат/vision/аудио/генерация изображений
    memory.py                  # скользящее окно контекста диалога
    scheduler.py                # APScheduler: напоминания, очистка кэша
    plugins/                     # автозагружаемые плагины (base.py, loader.py, ...)
    handlers/
        business.py                # учёт Business Connection ("Чат-боты")
        access.py                   # определение владельца / whitelist / blacklist
        autoresponder.py              # AI-ответы клиентам
        commands.py                    # self-команды владельца
        media.py                        # OCR/voice/analyze/imagine
        antispam.py, dnd.py, notes.py, reminders.py, search.py
    utils/                                # rate limiter, парсер времени, текстовые утилиты
    models/                                # SQLAlchemy ORM модели (+ business_connection.py)
    cache/                                  # файловый TTL-кэш
```

## Быстрый старт (локально)

### 1. Создайте бота и получите BOT_TOKEN

В Telegram напишите **@BotFather** → `/newbot` → следуйте инструкциям →
получите токен вида `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.

### 2. Подключите бота через функцию «Чат-боты»

В приложении Telegram: **Настройки → Telegram Business → Чат-боты** →
выберите вашего бота → включите нужные права (отвечать за вас, читать
сообщения и т.д.). Функция Telegram Business доступна с активной
подпиской Telegram Premium/Business.

> Если у вас нет доступа к Telegram Business, можно тестировать ассистента
> и в режиме обычных личных сообщений боту — тогда добавьте свой Telegram
> ID в `OWNER_IDS`, и self-команды будут работать в личном чате с ботом.

### 3. Получите GEMINI_API_KEY

На https://aistudio.google.com/apikey создайте API-ключ Google AI Studio.

### 4. Настройте .env

```bash
cp .env.example .env
# впишите BOT_TOKEN, GEMINI_API_KEY, OWNER_IDS и т.д.
```

### 5. Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m assistant.main
```

## Запуск в Docker

```bash
cp .env.example .env   # заполните значения
docker compose up -d --build
docker compose logs -f
```

В Docker-режиме процесс работает непрерывно (`RUN_DURATION_SECONDS`
переопределён в `docker-compose.yml` на очень большое значение), в
отличие от GitHub Actions, где job живёт ограниченное время.

## Запуск в GitHub Actions

1. В настройках репозитория → **Settings → Secrets and variables →
   Actions → Secrets** добавьте:
   - `BOT_TOKEN`
   - `OWNER_IDS` (например `123456789,987654321`, опционально)
   - `GEMINI_API_KEY`

2. По желанию, в **Variables** можно задать `RUN_DURATION_SECONDS`,
   `LOG_LEVEL`, `WHITELIST_MODE`, `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL` —
   если не заданы, используются значения по умолчанию из `config.py`.

3. Workflow `.github/workflows/bot.yml`:
   - запускается по `cron: "*/5 * * * *"` (каждые 5 минут);
   - можно запустить вручную через **Actions → Telegram AI Assistant
     → Run workflow** (`workflow_dispatch`);
   - устанавливает зависимости, запускает `python -m assistant.main`;
   - при ошибке (ненулевой код возврата) job помечается как **failed**;
   - логи при падении сохраняются как artifact (`assistant-logs-*`).

4. **Важно про хранение состояния.** GitHub Actions runner —
   эфемерная машина: файловая система не сохраняется между запусками
   сама по себе. Workflow использует `actions/cache` для
   персистентности `data/assistant.db` между запусками (лучшее
   доступное решение на голом Actions). Для полностью надёжного
   постоянного хранилища в проде рекомендуется self-host (Docker на
   VPS) вместо GitHub Actions, либо вынести SQLite на внешний volume.

## Переменные окружения

Полный список — в `.env.example`. Обязательные: `BOT_TOKEN`,
`GEMINI_API_KEY`. Остальные — с безопасными значениями по умолчанию.

## Безопасность

- `BOT_TOKEN` и `GEMINI_API_KEY` никогда не коммитятся — только через
  `.env` (локально, в `.gitignore`) или GitHub Secrets.
- `BOT_TOKEN` даёт полный доступ к управлению ботом — храните его как
  пароль; при компрометации немедленно отзовите токен через
  @BotFather → `/revoke`.
- Отключить функцию «Чат-боты» для этого бота можно в любой момент в
  Настройках Telegram Business — доступ к вашим чатам будет немедленно
  прекращён.
- Контейнер в Dockerfile запускается от непривилегированного
  пользователя `appuser`.

## Разработка плагинов

Создайте файл в `assistant/plugins/your_plugin.py`:

```python
from aiogram import Dispatcher, F, Router
from aiogram.types import Message

from assistant.handlers.access import is_message_from_owner
from assistant.plugins.base import Plugin


class YourPlugin(Plugin):
    name = "your_plugin"
    description = "Что делает плагин"

    def register(self, dp: Dispatcher) -> None:
        router = Router(name="plugin_your_plugin")

        async def handler(message: Message) -> None:
            if not await is_message_from_owner(message):
                return
            await message.reply("Привет из плагина!")

        pattern = r"(?i)^/yourcmd"
        router.message.register(handler, F.text.regexp(pattern))
        router.business_message.register(handler, F.text.regexp(pattern))
        dp.include_router(router)
```

Плагин будет автоматически найден и зарегистрирован при старте
(`plugins/loader.py`), если `PLUGINS_ENABLED=true`.

## Лицензия

Используйте и модифицируйте свободно для личных нужд.
