"""Schemas Pydantic do contrato de API de categorias (SPEC-002 / RF01)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryPublic(BaseModel):
    """Categoria disponível para associar a um post (RF01)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class CategoryInput(BaseModel):
    """Payload de `POST /api/admin/categories` (RF09)."""

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name não pode ser vazio ou só espaços.")
        return stripped
