"""Router administrativo de posts (SPEC-002) — `/api/admin/posts*`.

Apenas orquestração HTTP (parsing de request/query params, status codes);
toda a regra de negócio vive em `app.services.post_service`. Todas as rotas
exigem autenticação com papel `editor` ou `admin` (RF01/RF03/RF04/RF05).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.models.post import PostStatus
from app.models.user import User
from app.schemas.post import PostAdmin, PostAdminPage, PostCreate, PostUpdate
from app.services import post_service
from app.services.post_service import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/api/admin/posts", tags=["admin-posts"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post não encontrado.")


@router.post("", response_model=PostAdmin, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> PostAdmin:
    """`POST /api/admin/posts` — RF01/RF02."""

    post = await post_service.create_post(db, payload)
    return PostAdmin.model_validate(post)


@router.put("/{post_id}", response_model=PostAdmin)
async def update_post(
    post_id: str,
    payload: PostUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> PostAdmin:
    """`PUT /api/admin/posts/{id}` — RF03. `404` se o post não existir."""

    post = await post_service.update_post(db, post_id, payload)
    if post is None:
        raise _NOT_FOUND
    return PostAdmin.model_validate(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
) -> None:
    """`DELETE /api/admin/posts/{id}` — RF04 (soft delete). `404` se não existir."""

    deleted = await post_service.delete_post(db, post_id)
    if not deleted:
        raise _NOT_FOUND


@router.get("", response_model=PostAdminPage)
async def list_posts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("editor", "admin")),
    status_filter: PostStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PostAdminPage:
    """`GET /api/admin/posts?status=&category=&q=&page=&page_size=` — RF05."""

    items, total = await post_service.list_posts_admin(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        category_id=category,
        q=q,
        include_deleted=include_deleted,
    )
    return PostAdminPage(
        items=[PostAdmin.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
