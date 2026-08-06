"""Router administrativo de configuração da IA (SPEC-004) — `/api/admin/ai-settings`.

Apenas orquestração HTTP; toda a lógica vive em
`app.services.ai_settings_service`. Exige autenticação `editor`/`admin`
(mesmo padrão de `posts_admin.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai_settings import AiSettingsInput, AiSettingsPublic
from app.services import ai_settings_service

router = APIRouter(prefix="/api/admin/ai-settings", tags=["admin-ai-settings"])


@router.get("", response_model=AiSettingsPublic)
async def get_ai_settings(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> AiSettingsPublic:
    """`GET /api/admin/ai-settings` — configuração atual (chave mascarada)."""

    settings = await ai_settings_service.get_ai_settings(db)
    return ai_settings_service.to_public(settings, get_settings())


@router.put("", response_model=AiSettingsPublic)
async def update_ai_settings(
    payload: AiSettingsInput,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> AiSettingsPublic:
    """`PUT /api/admin/ai-settings` — cria ou atualiza a configuração."""

    settings = await ai_settings_service.save_ai_settings(db, payload)
    return ai_settings_service.to_public(settings, get_settings())
