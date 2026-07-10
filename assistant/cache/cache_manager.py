"""
cache/cache_manager.py
Простой файловый кэш с TTL. Используется, например, для кэширования
переводов/суммаризаций одинаковых текстов, чтобы не тратить AI-квоту
повторно в рамках короткоживущих запусков GitHub Actions.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from assistant.config import config


class FileCache:
    def __init__(self, directory: str | None = None, default_ttl: int = 3600) -> None:
        self.dir = Path(directory or config.cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    @staticmethod
    def _key_to_path(key: str, base_dir: Path) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return base_dir / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._key_to_path(key, self.dir)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if payload.get("expires_at", 0) < time.time():
            path.unlink(missing_ok=True)
            return None
        return payload.get("value")

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        path = self._key_to_path(key, self.dir)
        payload = {
            "expires_at": time.time() + (ttl if ttl is not None else self.default_ttl),
            "value": value,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def cleanup_expired(self) -> int:
        removed = 0
        now = time.time()
        for path in self.dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("expires_at", 0) < now:
                    path.unlink(missing_ok=True)
                    removed += 1
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)
                removed += 1
        return removed


cache = FileCache()
