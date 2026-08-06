"""Regra de negócio de categorias (SPEC-002 / RF01).

RF01 exige que todo post tenha uma categoria, mas a SPEC-002 não define um
endpoint de gestão de categorias — este módulo expõe só a listagem
necessária para o `PostEditor` (frontend) oferecer um seletor de categorias
já existentes em vez de exigir que o editor digite um UUID de cabeça (o que
antes fazia `POST /api/admin/posts` falhar com violação de FK sempre que o
valor digitado não correspondesse a uma categoria real).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def list_categories(db: AsyncSession) -> list[Category]:
    """Lista todas as categorias, ordenadas por nome."""

    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())
