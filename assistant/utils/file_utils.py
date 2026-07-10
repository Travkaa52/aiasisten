"""
utils/file_utils.py
Работа с временными файлами (скачанные медиа перед обработкой).
Все операции идут через executor, чтобы не блокировать event loop.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

TMP_DIR = Path(tempfile.gettempdir()) / "assistant_media"
TMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_TEXT_FILE_BYTES = 200_000  # не читаем в память файлы больше 200KB как текст


def new_tmp_path(suffix: str = "") -> Path:
    return TMP_DIR / f"{uuid.uuid4().hex}{suffix}"


async def read_text_file(path: Path, max_bytes: int = MAX_TEXT_FILE_BYTES) -> str:
    loop = asyncio.get_running_loop()

    def _read() -> str:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")

    return await loop.run_in_executor(None, _read)


async def cleanup_tmp(path: Path) -> None:
    loop = asyncio.get_running_loop()

    def _unlink() -> None:
        path.unlink(missing_ok=True)

    await loop.run_in_executor(None, _unlink)
