"""Schemas Pydantic do contrato de API de upload de mídia (SPEC-005)."""

from __future__ import annotations

from pydantic import BaseModel


class CoverImageUploadResult(BaseModel):
    """Resposta de `POST /api/admin/media/cover-image`."""

    url: str
