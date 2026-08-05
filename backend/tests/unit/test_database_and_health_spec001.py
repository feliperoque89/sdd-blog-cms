"""Testes unitários de infraestrutura básica (`app.core.database`, `app.main`).

Não fazem parte diretamente dos critérios de aceite de SPEC-001, mas cobrem
peças de infraestrutura que a spec depende (a dependency `get_db` de
produção, e o healthcheck usado por orquestração de containers), conforme
`specs/TESTING.md` (mínimo 80% de cobertura em `app/`).
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app as fastapi_app


async def test_get_db_yields_an_async_session_spec001() -> None:
    session_generator = get_db()

    session = await session_generator.__anext__()
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session_generator.aclose()


async def test_health_endpoint_returns_ok_spec001() -> None:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as probe_client:
        response = await probe_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
