"""Schemas Pydantic do contrato de API de categorias (SPEC-002 / RF01)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CategoryPublic(BaseModel):
    """Categoria disponível para associar a um post (RF01)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
