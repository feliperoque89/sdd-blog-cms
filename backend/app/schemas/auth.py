"""Schemas Pydantic do contrato de API de autenticação (SPEC-001)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Payload de `POST /api/auth/login`."""

    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Dados públicos do usuário autenticado (nunca inclui senha/hash/token).

    Contrato de API (SPEC-001):
    ```json
    { "id": "uuid", "name": "string", "role": "admin" | "editor" }
    ```
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: UserRole
