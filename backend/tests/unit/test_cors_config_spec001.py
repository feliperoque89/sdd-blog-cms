"""Testes unitários — CORS (SPEC-001).

Necessário para o frontend (origem diferente do backend — ex.:
localhost:3000 vs. localhost:8000) conseguir chamar `/api/auth/*` com
cookies httpOnly. Achado rodando o app real (backend + frontend Next.js)
num navegador de verdade: sem `CORSMiddleware`, toda chamada do frontend
falha no preflight `OPTIONS` antes mesmo de chegar no endpoint — invisível
para o resto da suíte, que sempre chama a app FastAPI diretamente via
`ASGITransport` (httpx.AsyncClient), sem o enforcement de CORS de um
navegador real.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import get_settings


async def test_allowed_origin_gets_cors_headers_on_preflight_spec001(
    client: AsyncClient,
) -> None:
    allowed_origin = get_settings().cors_allowed_origins[0]

    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


async def test_disallowed_origin_does_not_get_cors_headers_spec001(
    client: AsyncClient,
) -> None:
    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"
