"""Schemas Pydantic do contrato de API de posts (SPEC-002)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.post import PostStatus


class PostCreate(BaseModel):
    """Payload de `POST /api/admin/posts` (RF01)."""

    title: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)
    category_id: str
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    status: PostStatus = PostStatus.DRAFT


class PostUpdate(BaseModel):
    """Payload de `PUT /api/admin/posts/{id}` — campos parciais (RF03).

    Todos os campos são opcionais: apenas os enviados explicitamente pelo
    cliente (`model_dump(exclude_unset=True)`, feito em
    `app.services.post_service.update_post`) são alterados no post existente.
    """

    title: str | None = Field(default=None, min_length=1)
    content_markdown: str | None = Field(default=None, min_length=1)
    category_id: str | None = None
    tags: list[str] | None = None
    cover_image_url: str | None = None
    status: PostStatus | None = None


class _PostBase(BaseModel):
    """Campos comuns às respostas pública e administrativa de um post."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    slug: str
    content_markdown: str
    category_id: str
    tags: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    status: PostStatus
    published_at: datetime | None = None
    created_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _default_tags(cls, value: list[str] | None) -> list[str]:
        """Normaliza `tags` nulo (nunca setado no banco) para lista vazia."""

        return value if value is not None else []


class PostPublic(_PostBase):
    """Post no contrato público (`GET /api/posts`, `GET /api/posts/{slug}`)."""


class PostAdmin(_PostBase):
    """Post no contrato administrativo — inclui `deleted_at` (RF04)."""

    deleted_at: datetime | None = None


class PostPublicPage(BaseModel):
    """Envelope de paginação da listagem pública (RNF02)."""

    items: list[PostPublic]
    total: int
    page: int
    page_size: int


class PostAdminPage(BaseModel):
    """Envelope de paginação da listagem administrativa (RF05/RNF02)."""

    items: list[PostAdmin]
    total: int
    page: int
    page_size: int
