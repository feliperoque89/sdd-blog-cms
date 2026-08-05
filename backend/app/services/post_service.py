"""Regra de negócio de CRUD de posts (SPEC-002).

Router (`app.api.posts_admin`/`app.api.posts_public`) fica responsável
apenas por HTTP (status codes, query params); toda a lógica de negócio —
geração de slug único, soft delete, filtros e paginação — vive aqui.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, PostStatus
from app.schemas.post import PostCreate, PostUpdate

# RNF02: paginação obrigatória, tamanho padrão 10, máximo 50.
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Gera um slug URL-safe a partir de um título (RF02).

    Remove acentos, força minúsculas e substitui qualquer sequência de
    caracteres não alfanuméricos por um único hífen (ex.: "Como usar SDD"
    -> "como-usar-sdd").
    """

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_INVALID_CHARS.sub("-", ascii_text.lower()).strip("-")
    return slug or "post"


async def _slug_exists(db: AsyncSession, slug: str) -> bool:
    result = await db.execute(select(Post.id).where(Post.slug == slug))
    return result.scalar_one_or_none() is not None


async def generate_unique_slug(db: AsyncSession, title: str) -> str:
    """Gera um slug único a partir do título, com sufixo numérico em colisão.

    Critério de aceite 1/2 da SPEC-002: "Como usar SDD" -> "como-usar-sdd";
    em caso de colisão, "como-usar-sdd-2", "como-usar-sdd-3", etc.
    """

    base_slug = slugify(title)
    candidate = base_slug
    suffix = 2
    while await _slug_exists(db, candidate):
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


async def create_post(db: AsyncSession, data: PostCreate) -> Post:
    """Cria um post, gerando um slug único a partir do título (RF01/RF02)."""

    slug = await generate_unique_slug(db, data.title)
    now = datetime.now(UTC)
    post = Post(
        id=str(uuid.uuid4()),
        title=data.title,
        slug=slug,
        content_markdown=data.content_markdown,
        category_id=data.category_id,
        tags=list(data.tags),
        cover_image_url=data.cover_image_url,
        status=data.status,
        published_at=now if data.status == PostStatus.PUBLISHED else None,
        created_at=now,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def get_post_by_id(db: AsyncSession, post_id: str) -> Post | None:
    """Busca um post pelo id, independentemente de status ou soft delete.

    Usado pelas rotas administrativas (`PUT`/`DELETE`), que precisam
    localizar o post mesmo que ele já esteja excluído ou em rascunho.
    """

    result = await db.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()


async def get_published_post_by_slug(db: AsyncSession, slug: str) -> Post | None:
    """Busca um post publicado e não excluído pelo slug (RF07).

    Retorna `None` (traduzido em `404` pelo router) se o slug não existir,
    se o post estiver em `draft` ou se tiver sido soft-deletado.
    """

    result = await db.execute(
        select(Post).where(
            Post.slug == slug,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def update_post(db: AsyncSession, post_id: str, data: PostUpdate) -> Post | None:
    """Atualiza apenas os campos enviados em `data` (RF03).

    Retorna `None` se o post não existir. Ao transicionar o status para
    `published`, preenche `published_at` (se ainda não preenchido) para que
    o post apareça corretamente ordenado na listagem pública (RF06).
    """

    post = await get_post_by_id(db, post_id)
    if post is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    if update_data.get("status") == PostStatus.PUBLISHED and post.published_at is None:
        post.published_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post_id: str) -> bool:
    """Soft delete de um post (RF04): marca `deleted_at`, não remove a linha.

    Retorna `False` se o post não existir (traduzido em `404` pelo router).
    """

    post = await get_post_by_id(db, post_id)
    if post is None:
        return False

    post.deleted_at = datetime.now(UTC)
    await db.commit()
    return True


async def _paginate(
    db: AsyncSession,
    conditions: list[Any],
    *,
    order_by: Any,
    page: int,
    page_size: int,
) -> tuple[list[Post], int]:
    base_stmt = select(Post)
    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    items_stmt = base_stmt.order_by(order_by).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(items_stmt)
    items = list(result.scalars().all())

    return items, total


async def list_posts_admin(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status_filter: PostStatus | None = None,
    category_id: str | None = None,
    q: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[Post], int]:
    """Lista posts na área admin, com filtros de status/categoria/busca (RF05).

    Por padrão exclui posts soft-deletados, a menos que `include_deleted`
    seja `True` (critério de aceite 4).
    """

    conditions: list[Any] = []
    if not include_deleted:
        conditions.append(Post.deleted_at.is_(None))
    if status_filter is not None:
        conditions.append(Post.status == status_filter)
    if category_id is not None:
        conditions.append(Post.category_id == category_id)
    if q:
        conditions.append(Post.title.ilike(f"%{q}%"))

    return await _paginate(
        db, conditions, order_by=Post.created_at.desc(), page=page, page_size=page_size
    )


async def list_posts_public(
    db: AsyncSession, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
) -> tuple[list[Post], int]:
    """Lista posts publicados e não excluídos, ordenados por publicação (RF06)."""

    conditions: list[Any] = [Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None)]
    return await _paginate(
        db, conditions, order_by=Post.published_at.desc(), page=page, page_size=page_size
    )
