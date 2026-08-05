"""Infraestrutura de acesso a banco de dados (SQLAlchemy 2.x async).

Em produção, `DATABASE_URL` aponta para MySQL (via `asyncmy`), conforme
`specs/ARCHITECTURE.md`. Em testes unitários, a dependency `get_db` é
substituída via `app.dependency_overrides` por uma sessão SQLite in-memory
(ver `backend/tests/conftest.py`) — o engine/sessionmaker definidos aqui não
chegam a ser exercitados nesse cenário, mas precisam existir e ser
importáveis para que `Base` e `get_db` estejam disponíveis.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos SQLAlchemy."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI que fornece uma `AsyncSession` por requisição."""

    async with AsyncSessionLocal() as session:
        yield session
