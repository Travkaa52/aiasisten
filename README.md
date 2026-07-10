# Telegram AI Assistant

Production-ready персональный AI-ассистент для Telegram на **Telethon**
(user-account, не Bot API), с памятью диалога, автоответчиком,
плагинами и полным набором утилитарных функций. Работает как
long-running процесс (Docker/self-host) либо как короткоживущий job в
**GitHub Actions**, запускаемый по расписанию каждые 5 минут.

## Возможности

| Категория | Что делает |
|---|---|
| AI Assistant | Диалог с учётом контекста памяти (`memory.py`) через Anthropic Claude |
| Автоответы | Автоматически отвечает на входящие сообщения (`handlers/autoresponder.py`) |
| Переписывание | `/rewrite <стиль>` в ответ на сообщение |
| Перевод | `/translate <язык>` в ответ на сообщение |
| Суммаризация | `/summarize` в ответ на сообщение |
| Напоминания | `/remind`, `/reminders`, `/unremind` — доставка через APScheduler |
| Заметки | `/note add|list|get|del` |
| Поиск | `/search <запрос>` по истории сообщений |
| OCR | `/ocr` в ответ на фото (через Claude vision) |
| Voice-to-Text | `/voice` в ответ на голосовое (через OpenAI Whisper) |
| Генерация изображений | `/imagine <промпт>` (через OpenAI Images) |
| Анализ файлов | `/analyze` в ответ на документ |
| Плагины | Автозагрузка из `assistant/plugins/` |
| Статистика | `/stats` |
| Антиспам | Sliding-window rate limit + авто-блэклист |
| Whitelist/Blacklist | `/whitelist`, `/blacklist` |
| Do Not Disturb | `/dnd on|off|status` |

Команды отправляются **из вашего же аккаунта** (это userbot на
Telethon, а не отдельный бот) — например, ответом на сообщение в
Saved Messages или любом чате.

## Архитектура

```
assistant/
    main.py          # точка входа, подключение, graceful run/shutdown
    config.py         # конфигурация из .env / переменных окружения
    database.py       # async SQLAlchemy engine + сессии (SQLite)
    logger.py          # loguru: консоль + ротируемые файлы
    ai.py              # Anthropic (чат/перевод/OCR) + OpenAI (image/voice)
    memory.py           # скользящее окно контекста диалога
    scheduler.py         # APScheduler: напоминания, очистка кэша
    plugins/               # автозагружаемые плагины (base.py, loader.py, ...)
    handlers/               # обработчики Telethon-событий
    utils/                    # rate limiter, парсер времени, текстовые утилиты
    models/                     # SQLAlchemy ORM модели
    cache/                        # файловый TTL-кэш
    sessions/                       # (пусто; сессия хранится в Secrets, не в файле)
```

## Быстрый старт (локально)

### 1. Получите API_ID / API_HASH

На https://my.telegram.org → **API Development Tools** → создайте
приложение, получите `api_id` и `api_hash`.

### 2. Сгенерируйте StringSession

```bash
pip install telethon
python - <<'PY'
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: "))
api_hash = input("API_HASH: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nВаша SESSION строка (сохраните в секретах, никому не передавайте):\n")
    print(client.session.save())
PY
```

Скрипт запросит номер телефона и код подтверждения из Telegram —
это одноразовая авторизация, после которой сессия сохраняется в
виде строки.

### 3. Настройте .env

```bash
cp .env.example .env
# впишите API_ID, API_HASH, SESSION, OWNER_IDS, ANTHROPIC_API_KEY и т.д.
```

### 4. Запуск

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
   - `API_ID`
   - `API_HASH`
   - `SESSION`
   - `OWNER_IDS` (например `123456789,987654321`)
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY` (опционально, для `/imagine` и `/voice`)

2. По желанию, в **Variables** можно задать `RUN_DURATION_SECONDS`,
   `LOG_LEVEL`, `WHITELIST_MODE`, `ANTHROPIC_MODEL` — если не заданы,
   используются значения по умолчанию из `config.py`.

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

Полный список — в `.env.example`. Обязательные: `API_ID`, `API_HASH`,
`SESSION`. Остальные — с безопасными значениями по умолчанию.

## Безопасность

- Токены и `SESSION` никогда не коммитятся — только через `.env`
  (локально, в `.gitignore`) или GitHub Secrets.
- `SESSION` даёт полный доступ к аккаунту Telegram — храните её как
  пароль, не публикуйте, при компрометации немедленно завершите все
  сессии в Telegram (Settings → Devices → Terminate all sessions) и
  сгенерируйте новую.
- Контейнер в Dockerfile запускается от непривилегированного
  пользователя `appuser`.

## Разработка плагинов

Создайте файл в `assistant/plugins/your_plugin.py`:

```python
from telethon import TelegramClient, events
from assistant.plugins.base import Plugin

class YourPlugin(Plugin):
    name = "your_plugin"
    description = "Что делает плагин"

    def register(self, client: TelegramClient) -> None:
        @client.on(events.NewMessage(outgoing=True, pattern=r"(?i)^/yourcmd"))
        async def handler(event):
            await event.reply("Привет из плагина!")
```

Плагин будет автоматически найден и зарегистрирован при старте
(`plugins/loader.py`), если `PLUGINS_ENABLED=true`.

## Лицензия

Используйте и модифицируйте свободно для личных нужд.
