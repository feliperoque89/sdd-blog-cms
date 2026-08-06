"""Router administrativo de mídia (SPEC-005 / RF01) — `/api/admin/media`.

Apenas orquestração HTTP: valida tipo/tamanho do arquivo (RF02/RF03), gera
uma chave opaca (RF04) e delega a gravação a
`app.services.media_storage_service`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_role
from app.core.config import get_settings
from app.models.user import User
from app.schemas.media import CoverImageUploadResult
from app.services.image_validation import ALLOWED_IMAGE_TYPES, detect_image_content_type
from app.services.media_storage_service import (
    MediaStorageClient,
    MediaStorageError,
    get_media_storage_client,
)

router = APIRouter(prefix="/api/admin/media", tags=["admin-media"])

#: RF03 — 5MB.
_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

_INVALID_TYPE_ERROR = "Tipo de arquivo não permitido. Envie uma imagem JPEG, PNG ou WebP."
_TOO_LARGE_ERROR = "Arquivo maior que o limite de 5MB."
_GENERIC_STORAGE_ERROR = "Não foi possível enviar a imagem no momento. Tente novamente mais tarde."


@router.post(
    "/cover-image",
    response_model=CoverImageUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cover_image(
    file: UploadFile = File(...),
    storage_client: MediaStorageClient = Depends(get_media_storage_client),
    _user: User = Depends(require_role("editor", "admin")),
) -> CoverImageUploadResult:
    """`POST /api/admin/media/cover-image` — envia a imagem de capa (RF01).

    Tipo real do arquivo é detectado por assinatura (RF02), nunca confiando
    só no `Content-Type` declarado. A chave gravada no bucket é sempre
    gerada pelo backend (RF04) — nunca o nome original do arquivo.
    """

    data = await file.read(_MAX_FILE_SIZE_BYTES + 1)
    if len(data) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_TOO_LARGE_ERROR
        )

    content_type = detect_image_content_type(data)
    if content_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_INVALID_TYPE_ERROR
        )

    extension = ALLOWED_IMAGE_TYPES[content_type]
    key = f"cover-images/{uuid.uuid4()}.{extension}"

    try:
        await storage_client.upload(key=key, data=data, content_type=content_type)
    except MediaStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=_GENERIC_STORAGE_ERROR
        ) from exc

    settings = get_settings()
    url = f"{settings.media_storage_public_base_url.rstrip('/')}/{key}"
    return CoverImageUploadResult(url=url)
