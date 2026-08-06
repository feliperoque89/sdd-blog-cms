"""Fixtures compartilhadas para os testes unitários de backend.

Segue specs/TESTING.md:
- Cliente de teste: `httpx.AsyncClient` com `ASGITransport` contra a app
  FastAPI real (`app.main.app`), sem subir servidor de verdade.
- Banco: SQLite in-memory (via SQLAlchemy async + aiosqlite), isolado por
  teste.
- Redis (blacklist de refresh token e rate limiter de login) é abstraído por
  interfaces em `app.services.*` e substituído aqui por fakes 100% em
  memória — nenhum teste unitário toca um Redis de verdade.

Nada neste arquivo implementa `app/`; ele apenas assume a estrutura de
módulos que o backend-builder criará para satisfazer
`tests/unit/test_auth_service_spec001.py` (fase RED do TDD).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Variáveis de ambiente precisam existir ANTES de qualquer `import app...`,
# pois a Settings (pydantic BaseSettings) do backend deve lê-las no import.
# Valores dummy, seguros apenas para teste.
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-do-not-use-in-prod")
os.environ.setdefault("JWT_EXPIRES_MIN", "60")
os.environ.setdefault("JWT_REFRESH_EXPIRES_DAYS", "7")
os.environ.setdefault("RATE_LIMIT_LOGIN_MAX_ATTEMPTS", "5")
os.environ.setdefault("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("COOKIE_SECURE", "false")
# SPEC-005 — nunca usado de verdade (a suíte sempre faz override de
# `get_media_storage_client` por um fake), só precisa existir para a
# `Settings` (pydantic) construir sem erro.
os.environ.setdefault("MEDIA_STORAGE_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("MEDIA_STORAGE_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MEDIA_STORAGE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("MEDIA_STORAGE_PUBLIC_BASE_URL", "http://localhost:9000/media")

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.models.user import User, UserRole
from app.services.rate_limiter import get_login_rate_limiter
from app.services.token_blacklist import get_token_blacklist
from tests.factories import DEFAULT_RAW_PASSWORD, UserFactory


# ---------------------------------------------------------------------------
# Fakes das dependências de infraestrutura (Redis em produção).
# ---------------------------------------------------------------------------
class InMemoryTokenBlacklist:
    """Fake de `app.services.token_blacklist.TokenBlacklist`.

    Em produção, a blacklist de refresh tokens (RF06) vive no Redis com TTL.
    Aqui é só um dict em memória — suficiente e determinístico para testes
    unitários, sem qualquer chamada de rede.
    """

    def __init__(self) -> None:
        self._store: dict[str, datetime] = {}

    async def add(self, jti: str, ttl_seconds: int) -> None:
        self._store[jti] = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

    async def is_blacklisted(self, jti: str) -> bool:
        expires_at = self._store.get(jti)
        if expires_at is None:
            return False
        if expires_at < datetime.now(UTC):
            del self._store[jti]
            return False
        return True


class InMemoryLoginRateLimiter:
    """Fake de `app.services.rate_limiter.LoginRateLimiter` (RNF02).

    Contador de tentativas por chave (IP) em janela deslizante, todo em
    memória — substitui o Redis real usado em produção para rate limiting
    distribuído.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = {}

    async def is_allowed(self, key: str) -> bool:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=self.window_seconds)
        hits = [hit for hit in self._hits.get(key, []) if hit > window_start]
        allowed = len(hits) < self.max_attempts
        hits.append(now)
        self._hits[key] = hits
        return allowed


# ---------------------------------------------------------------------------
# Banco de dados (SQLite in-memory, isolado por teste)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# Fakes de infra expostos como fixtures (para inspeção direta nos testes,
# ex.: checar `token_blacklist.is_blacklisted(...)` após logout).
# ---------------------------------------------------------------------------
@pytest.fixture
def token_blacklist() -> InMemoryTokenBlacklist:
    return InMemoryTokenBlacklist()


@pytest.fixture
def login_rate_limiter() -> InMemoryLoginRateLimiter:
    return InMemoryLoginRateLimiter(max_attempts=5, window_seconds=60)


# ---------------------------------------------------------------------------
# App FastAPI com dependências de infra substituídas pelos fakes acima.
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app(db_session, token_blacklist, login_rate_limiter):
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_token_blacklist] = lambda: token_blacklist
    fastapi_app.dependency_overrides[get_login_rate_limiter] = lambda: login_rate_limiter

    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Usuários semeados no banco de teste.
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def seed_editor_user(db_session) -> tuple[User, str]:
    user = UserFactory.build(role=UserRole.EDITOR)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, DEFAULT_RAW_PASSWORD


@pytest_asyncio.fixture
async def seed_admin_user(db_session) -> tuple[User, str]:
    user = UserFactory.build(role=UserRole.ADMIN)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, DEFAULT_RAW_PASSWORD


@pytest.fixture
def raw_password_hash_factory():
    """Helper para testes de RNF01 que precisam gerar hashes ad-hoc."""

    return hash_password


# ---------------------------------------------------------------------------
# Clientes já autenticados (login real via `/api/auth/login`), reaproveitados
# por specs futuras cujas rotas exigem um usuário editor|admin (ex.: SPEC-002
# — CRUD de posts, `/api/admin/posts*`). Não dependem de nenhum módulo além
# dos já usados pelos testes de SPEC-001, então não têm risco de quebrar a
# suíte de autenticação caso outra spec ainda não esteja implementada.
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def editor_client(client: AsyncClient, seed_editor_user) -> AsyncClient:
    user, raw_password = seed_editor_user
    login_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert login_response.status_code == 200
    return client


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, seed_admin_user) -> AsyncClient:
    user, raw_password = seed_admin_user
    login_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert login_response.status_code == 200
    return client
