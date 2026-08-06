"""Client de storage de mídia (SPEC-005 — Upload de Imagem de Capa).

`MediaStorageClient` (Protocol) é a interface consumida por `app.api.media`.
Em testes unitários, `get_media_storage_client` é sempre substituída via
`app.dependency_overrides` por um fake 100% em memória
(`FakeMediaStorageClient`, em `tests/unit/test_media_upload_spec005.py`) —
nenhum teste chama um MinIO/S3 real (`specs/TESTING.md`).

`S3MediaStorageClient` é a implementação de produção, via `boto3` (MinIO é
S3-compatible). `boto3` é síncrono — cada chamada roda em thread separada
(`starlette.concurrency.run_in_threadpool`) para não bloquear o event loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import boto3
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class MediaStorageError(Exception):
    """Erro de comunicação com o storage de mídia (MinIO/S3).

    Levantada em qualquer falha ao gravar o objeto — quem chama (o router)
    traduz isso em `502` com mensagem genérica (RNF03), nunca propagando o
    detalhe interno (credenciais, mensagem de erro do SDK, etc.) — mesmo
    espírito de `AiClientError` (SPEC-003).
    """


class MediaStorageClient(Protocol):
    """Interface que qualquer implementação de storage de mídia deve satisfazer."""

    async def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        """Grava `data` no storage sob `key`, com o `content_type` informado.

        Implementações devem levantar `MediaStorageError` em caso de falha.
        """
        ...


class S3MediaStorageClient:
    """Implementação de produção de `MediaStorageClient` — grava no MinIO/S3."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self._bucket = bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload(self, *, key: str, data: bytes, content_type: str) -> None:
        try:
            await run_in_threadpool(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise MediaStorageError("Erro ao gravar arquivo no storage de mídia.") from exc


_s3_media_storage_client: S3MediaStorageClient | None = None


def get_media_storage_client() -> MediaStorageClient:  # pragma: no cover - implementação de produção não testada
    """Dependency FastAPI: fornece o client de storage de mídia.

    Override-ável em testes via
    `app.dependency_overrides[get_media_storage_client] = lambda: fake_instance`.
    Nunca instanciada nos testes unitários — ver docstring do módulo.
    """

    global _s3_media_storage_client
    if _s3_media_storage_client is None:
        settings = get_settings()
        _s3_media_storage_client = S3MediaStorageClient(
            endpoint_url=settings.media_storage_endpoint_url,
            access_key=settings.media_storage_access_key,
            secret_key=settings.media_storage_secret_key,
            bucket=settings.media_storage_bucket,
        )
    return _s3_media_storage_client
