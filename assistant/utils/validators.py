"""
utils/validators.py
Парсинг относительного/абсолютного времени для команды /remind и
базовая валидация ввода.
"""

from __future__ import annotations

import datetime as dt
import re

_RELATIVE_RE = re.compile(
    r"^(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$"
)
_ABSOLUTE_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


class TimeParseError(ValueError):
    pass


def parse_remind_time(raw: str) -> dt.datetime:
    """Поддерживает форматы:
    - относительный: '10m', '2h30m', '1d', '45s'
    - абсолютное время сегодня/завтра: '18:30' (если время уже прошло — берём завтра)
    Возвращает aware datetime в UTC.
    """
    raw = raw.strip().lower()
    now = dt.datetime.now(dt.timezone.utc)

    match = _RELATIVE_RE.match(raw)
    if match and any(match.groupdict().values()):
        parts = {k: int(v) for k, v in match.groupdict().items() if v}
        delta = dt.timedelta(
            days=parts.get("days", 0),
            hours=parts.get("hours", 0),
            minutes=parts.get("minutes", 0),
            seconds=parts.get("seconds", 0),
        )
        if delta.total_seconds() <= 0:
            raise TimeParseError("Длительность должна быть положительной.")
        return now + delta

    abs_match = _ABSOLUTE_TIME_RE.match(raw)
    if abs_match:
        hour = int(abs_match.group("hour"))
        minute = int(abs_match.group("minute"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise TimeParseError("Некорректное время суток.")
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += dt.timedelta(days=1)
        return candidate

    raise TimeParseError(
        "Не удалось распознать время. Примеры: '10m', '2h30m', '1d', '18:30'."
    )


def sanitize_text(text: str, max_len: int = 4000) -> str:
    text = text.strip()
    return text[:max_len]
