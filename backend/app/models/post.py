"""Modelo `Post` (SPEC-002 — CRUD de Posts).

Convenções:
- `slug`: gerado a partir do título pelo `app.services.post_service`, único
  na tabela (RF02).
- `tags`: lista simples de strings, persistida como coluna `JSON` — modelagem
  mais simples adequada para o escopo desta spec (sem necessidade de
  contagem/filtro por tag individual, apenas armazenar e devolver).
- `deleted_at`: soft delete (RF04). `NULL` significa "não excluído".
- `published_at`: preenchido quando o post é (ou passa a ser) `published`
  (RF06 — ordenação da listagem pública por data de publicação decrescente).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PostStatus(str, enum.Enum):
    """Status de um post (contrato de API: `"draft" | "published"`)."""

    DRAFT = "draft"
    PUBLISHED = "published"


class Post(Base):
    """Post de blog, redigido (ou revisado) por um editor/admin."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("categories.id"), nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(
            PostStatus,
            name="post_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PostStatus.DRAFT,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"Post(id={self.id!r}, slug={self.slug!r}, status={self.status!r})"
