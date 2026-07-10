"""
handlers/notes.py
Команды заметок:
  /note add <заголовок> | <текст>
  /note list
  /note get <id>
  /note del <id>
"""

from __future__ import annotations

from sqlalchemy import delete, select

from assistant.database import get_session
from assistant.models import Note


async def add_note(owner_id: int, title: str, content: str) -> Note:
    async with get_session() as session:
        note = Note(owner_id=owner_id, title=title.strip() or "Без названия", content=content.strip())
        session.add(note)
        await session.flush()
        await session.refresh(note)
        return note


async def list_notes(owner_id: int) -> list[Note]:
    async with get_session() as session:
        result = await session.execute(
            select(Note).where(Note.owner_id == owner_id).order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())


async def get_note(owner_id: int, note_id: int) -> Note | None:
    async with get_session() as session:
        result = await session.execute(
            select(Note).where(Note.owner_id == owner_id, Note.id == note_id)
        )
        return result.scalar_one_or_none()


async def delete_note(owner_id: int, note_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            delete(Note).where(Note.owner_id == owner_id, Note.id == note_id)
        )
        return result.rowcount > 0


def format_note_line(note: Note) -> str:
    return f"#{note.id} — {note.title} ({note.created_at:%Y-%m-%d %H:%M UTC})"
