"""Router administrativo de categorias (SPEC-002 / RF01) — `/api/admin/categories`.

Apenas leitura: permite que o `PostEditor` (frontend) ofereça um seletor de
categorias existentes ao criar/editar um post. Não há endpoint de
criação/edição de categoria — fora do escopo de SPEC-002 (ver "Fora de
escopo" da spec).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.category import CategoryPublic
from app.services import category_service

router = APIRouter(prefix="/api/admin/categories", tags=["admin-categories"])


@router.get("", response_model=list[CategoryPublic])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> list[CategoryPublic]:
    """`GET /api/admin/categories` — lista categorias para o seletor do `PostEditor`."""

    categories = await category_service.list_categories(db)
    return [CategoryPublic.model_validate(c) for c in categories]
