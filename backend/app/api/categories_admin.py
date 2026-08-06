"""Router administrativo de categorias (SPEC-002 / RF08/RF09) — `/api/admin/categories`.

`GET` (RF08): permite que o `PostEditor` (frontend) ofereça um seletor de
categorias existentes ao criar/editar um post. `POST` (RF09): cadastra uma
categoria nova direto na mesma tela, sem uma tela administrativa separada
de gestão de categorias — idempotente por nome (case-insensitive), nunca
cria duplicata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.category import CategoryInput, CategoryPublic
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


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryInput,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> CategoryPublic:
    """`POST /api/admin/categories` — cria a categoria `name` (RF09).

    `201` se criou uma categoria nova, `200` se já existia uma com esse nome
    (case-insensitive) — nunca cria duplicata.
    """

    category, created = await category_service.get_or_create_category(db, payload.name)
    if not created:
        response.status_code = status.HTTP_200_OK
    return CategoryPublic.model_validate(category)
