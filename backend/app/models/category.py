"""Modelo `Category` (SPEC-002 — CRUD de Posts)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Category(Base):
    """Categoria à qual um `Post` pertence (RF01)."""

    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"Category(id={self.id!r}, name={self.name!r})"
