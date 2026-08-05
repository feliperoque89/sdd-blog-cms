"""Testes unitários — R1 (SPEC-003 / achado do ai-safety-reviewer).

`ai-safety-reviewer` apontou ausência de autorização em nível de objeto em
`GET /api/posts/generate-draft/{job_id}`: qualquer editor autenticado
conseguia consultar (e ler o conteúdo gerado de) o job de QUALQUER outro
editor, bastando adivinhar/obter o `job_id` (um UUID, mas ainda assim uma
falha de "broken object level authorization" — OWASP API1:2023).

`app.services.ai_assistant_service.get_job_status_for_user` agora filtra por
`editor_id`: um editor só enxerga os próprios jobs; um admin enxerga
qualquer job. Em ambos os casos de "não encontrado"/"não autorizado" a API
responde `404` (nunca `403`), para não confirmar a terceiros a existência de
um job de outro usuário.

Não depende de nenhum override de IA (`get_ai_client`/`get_job_queue`/
`get_ai_rate_limiter`): os jobs são semeados diretamente no banco de teste
(via `db_session`), sem passar por `POST /api/posts/generate-draft` — o
endpoint de status (`GET`) só depende de `get_db` + autenticação, então a
fixture `app` padrão de `tests/conftest.py` (sem overrides de IA) é
suficiente.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.models.assistant_draft import AssistantDraft, JobStatus
from app.models.user import UserRole
from tests.factories import DEFAULT_RAW_PASSWORD, UserFactory

GENERATE_DRAFT_URL = "/api/posts/generate-draft"


async def _seed_done_job(db_session, *, editor_id: str) -> str:
    job = AssistantDraft(
        id=str(uuid.uuid4()),
        editor_id=editor_id,
        status=JobStatus.DONE,
        topic="Tópico de teste",
        tone="tecnico",
        keywords=["a", "b"],
        length="medium",
        result_title="Título gerado",
        result_content_markdown="# Conteúdo\n\nTexto de exemplo.",
        result_meta_description="Meta description de exemplo.",
        result_tags=["a", "b"],
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job.id


# ---------------------------------------------------------------------------
# Fixtures locais: clientes autenticados independentes (cada um com seu
# próprio `AsyncClient`/cookie jar), necessário para ter DOIS editores
# autenticados simultaneamente no mesmo teste — `editor_client`/`admin_client`
# de `tests/conftest.py` compartilham uma única instância de `client` por
# teste, então não servem para este cenário (editor A vs. editor B).
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def editor_a_client(app, seed_editor_user) -> AsyncIterator[AsyncClient]:
    user, raw_password = seed_editor_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        login_response = await ac.post(
            "/api/auth/login", json={"email": user.email, "password": raw_password}
        )
        assert login_response.status_code == 200
        yield ac


@pytest_asyncio.fixture
async def editor_b_client(app, db_session) -> AsyncIterator[AsyncClient]:
    user = UserFactory.build(role=UserRole.EDITOR)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        login_response = await ac.post(
            "/api/auth/login", json={"email": user.email, "password": DEFAULT_RAW_PASSWORD}
        )
        assert login_response.status_code == 200
        yield ac


@pytest_asyncio.fixture
async def admin_a_client(app, seed_admin_user) -> AsyncIterator[AsyncClient]:
    user, raw_password = seed_admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        login_response = await ac.post(
            "/api/auth/login", json={"email": user.email, "password": raw_password}
        )
        assert login_response.status_code == 200
        yield ac


# ---------------------------------------------------------------------------
# R1 — autorização em nível de objeto.
# ---------------------------------------------------------------------------
async def test_editor_cannot_view_job_of_another_editor_returns_404_spec003(
    editor_a_client: AsyncClient,
    editor_b_client: AsyncClient,
    db_session,
    seed_editor_user,
) -> None:
    user_a, _raw_password = seed_editor_user
    job_id = await _seed_done_job(db_session, editor_id=user_a.id)

    response = await editor_b_client.get(f"{GENERATE_DRAFT_URL}/{job_id}")

    assert response.status_code == 404
    # Não deve haver qualquer vazamento do conteúdo do job de outro editor.
    assert "Título gerado" not in response.text


async def test_editor_can_view_own_job_spec003(
    editor_a_client: AsyncClient, db_session, seed_editor_user
) -> None:
    user_a, _raw_password = seed_editor_user
    job_id = await _seed_done_job(db_session, editor_id=user_a.id)

    response = await editor_a_client.get(f"{GENERATE_DRAFT_URL}/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "done"


async def test_admin_can_view_job_of_any_editor_spec003(
    admin_a_client: AsyncClient, db_session, seed_editor_user
) -> None:
    user_a, _raw_password = seed_editor_user
    job_id = await _seed_done_job(db_session, editor_id=user_a.id)

    response = await admin_a_client.get(f"{GENERATE_DRAFT_URL}/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["result"]["title"] == "Título gerado"
