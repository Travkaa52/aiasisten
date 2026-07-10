"""
database.py
Асинхронный доступ к SQLite через SQLAlchemy 2.0 + aiosqlite.
Полностью неблокирующий: все запросы идут через AsyncSession.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from assistant.config import config
from assistant.logger import log
from assistant.models import Base

Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)

_engine = create_async_engine(
    f"sqlite+aiosqlite:///{config.db_path}",
    echo=False,
    future=True,
)

_session_factory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Создаёт все таблицы, если их ещё нет. Идемпотентно — безопасно
    вызывать на каждом запуске воркфлоу."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("База данных инициализирована: {}", config.db_path)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Контекстный менеджер сессии с автоматическим commit/rollback."""
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    await _engine.dispose()
    log.info("Соединение с БД закрыто.")
