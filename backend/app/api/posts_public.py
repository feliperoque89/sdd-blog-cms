"""Router público de posts (SPEC-002) — `/api/posts*`.

Apenas orquestração HTTP; toda a regra de negócio vive em
`app.services.post_service`. Não exige autenticação (RF06/RF07).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.post import PostPublic, PostPublicPage
from app.services import post_service
from app.services.post_service import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/api/posts", tags=["posts"])

# RNF01: resposta cacheável. O valor exato não é definido pela spec; 60s é um
# TTL conservador para uma listagem que muda com publicações de posts.
_PUBLIC_LISTING_CACHE_CONTROL = "public, max-age=60"


@router.get("", response_model=PostPublicPage)
async def list_posts(
    response: Response,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PostPublicPage:
    """`GET /api/posts?page=&page_size=` — RF06."""

    items, total = await post_service.list_posts_public(db, page=page, page_size=page_size)
    response.headers["Cache-Control"] = _PUBLIC_LISTING_CACHE_CONTROL
    return PostPublicPage(
        items=[PostPublic.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{slug}", response_model=PostPublic)
async def get_post_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> PostPublic:
    """`GET /api/posts/{slug}` — RF07. `404` se não existir ou não publicado."""

    post = await post_service.get_published_post_by_slug(db, slug)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post não encontrado.")
    return PostPublic.model_validate(post)
