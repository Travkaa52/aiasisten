"""
models/base.py
Общий declarative base для всех ORM-моделей проекта.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
