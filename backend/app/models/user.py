"""Modelo `User` (SPEC-001 — autenticação de Admin/Editor)."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    """Papéis de usuário suportados (contrato de API: `"admin" | "editor"`)."""

    ADMIN = "admin"
    EDITOR = "editor"


class User(Base):
    """Usuário da área administrativa (admin ou editor)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls]
        ),
        nullable=False,
        default=UserRole.EDITOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"User(id={self.id!r}, email={self.email!r}, role={self.role!r})"
