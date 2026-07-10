"""
utils/text_utils.py
Вспомогательные функции для работы с текстом.
"""

from __future__ import annotations

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def chunk_text(text: str, size: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает длинный текст на части, безопасные для отправки в Telegram,
    стараясь резать по границам строк, а не посреди слова."""
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > size:
            if current:
                chunks.append(current)
            if len(line) > size:
                for i in range(0, len(line), size):
                    chunks.append(line[i : i + size])
                current = ""
            else:
                current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


def strip_command(text: str) -> str:
    """Убирает первое слово-команду (/note, /reminder ...) и возвращает остаток."""
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def is_command(text: str, name: str) -> bool:
    text = text.strip()
    if not text.startswith("/"):
        return False
    first_word = text.split(maxsplit=1)[0]
    command = first_word[1:].split("@")[0]  # поддержка /note@botname (на всякий случай)
    return command.lower() == name.lower()
