"""Testes unitários — `POST /api/admin/media/cover-image` (SPEC-005).

`get_media_storage_client` é substituída por `FakeMediaStorageClient` (100%
em memória) — nenhum teste unitário fala com um MinIO/S3 real
(`specs/TESTING.md`), mesmo padrão de `FakeAiClient` em
`test_ai_assistant_service_spec003.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app as fastapi_app
from app.services.media_storage_service import MediaStorageError, get_media_storage_client
from app.services.rate_limiter import get_login_rate_limiter
from app.services.token_blacklist import get_token_blacklist

_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32
_PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 32


class FakeMediaStorageClient:
    """Fake 100% em memória de `MediaStorageClient` — nunca toca um MinIO real."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, bytes, str]] = []

    async def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        if self.should_fail:
            raise MediaStorageError("Falha simulada de storage.")
        self.calls.append((key, data, content_type))


@pytest_asyncio.fixture
async def fake_media_storage_client() -> FakeMediaStorageClient:
    return FakeMediaStorageClient()


@pytest_asyncio.fixture
async def app(db_session, token_blacklist, login_rate_limiter, fake_media_storage_client):
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_token_blacklist] = lambda: token_blacklist
    fastapi_app.dependency_overrides[get_login_rate_limiter] = lambda: login_rate_limiter
    fastapi_app.dependency_overrides[get_media_storage_client] = lambda: fake_media_storage_client

    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def editor_client(client: AsyncClient, seed_editor_user) -> AsyncClient:
    user, raw_password = seed_editor_user
    login_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert login_response.status_code == 200
    return client


async def test_upload_cover_image_accepts_jpeg_and_returns_url_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.jpg", _JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["url"]
    assert len(fake_media_storage_client.calls) == 1
    key, data, content_type = fake_media_storage_client.calls[0]
    assert content_type == "image/jpeg"
    assert data == _JPEG_BYTES
    assert body["url"].endswith(key)


async def test_upload_cover_image_accepts_png_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.png", _PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    assert fake_media_storage_client.calls[0][2] == "image/png"


async def test_upload_cover_image_accepts_webp_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.webp", _WEBP_BYTES, "image/webp")},
    )

    assert response.status_code == 201
    assert fake_media_storage_client.calls[0][2] == "image/webp"


async def test_upload_cover_image_generates_opaque_object_key_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("../../etc/passwd.jpg", _JPEG_BYTES, "image/jpeg")},
    )

    key = fake_media_storage_client.calls[0][0]
    # RF04: nunca o nome original do arquivo, nem path traversal.
    assert "passwd" not in key
    assert ".." not in key
    assert key.endswith(".jpg")


async def test_upload_cover_image_rejects_disallowed_file_type_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.jpg", _PDF_BYTES, "image/jpeg")},
    )

    assert response.status_code == 422
    assert fake_media_storage_client.calls == []


async def test_upload_cover_image_rejects_file_above_size_limit_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    oversized = _JPEG_BYTES + b"\x00" * (5 * 1024 * 1024)

    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.jpg", oversized, "image/jpeg")},
    )

    assert response.status_code == 422
    assert fake_media_storage_client.calls == []


async def test_upload_cover_image_without_authentication_returns_401_spec005(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.jpg", _JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 401


async def test_upload_cover_image_returns_502_on_storage_failure_spec005(
    editor_client: AsyncClient, fake_media_storage_client: FakeMediaStorageClient
) -> None:
    fake_media_storage_client.should_fail = True

    response = await editor_client.post(
        "/api/admin/media/cover-image",
        files={"file": ("capa.jpg", _JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 502
    body = response.json()
    # RNF03: mensagem genérica, nunca o detalhe interno da exceção.
    assert "Falha simulada" not in body["detail"]
