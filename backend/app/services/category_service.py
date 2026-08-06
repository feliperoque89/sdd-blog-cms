"""Regra de negócio de categorias (SPEC-002 / RF01/RF08/RF09).

RF01 exige que todo post tenha uma categoria. `list_categories` (RF08)
permite que o `PostEditor` (frontend) ofereça um seletor de categorias já
existentes em vez de exigir que o editor digite um UUID de cabeça (o que
antes fazia `POST /api/admin/posts` falhar com violação de FK sempre que o
valor digitado não correspondesse a uma categoria real). `get_or_create_category`
(RF09) permite cadastrar uma categoria nova direto na mesma tela, sem uma
tela administrativa separada de gestão de categorias.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def list_categories(db: AsyncSession) -> list[Category]:
    """Lista todas as categorias, ordenadas por nome."""

    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


async def get_category_by_name(db: AsyncSession, name: str) -> Category | None:
    """Busca uma categoria por nome, sem diferenciar maiúsculas/minúsculas."""

    result = await db.execute(select(Category).where(func.lower(Category.name) == name.lower()))
    return result.scalar_one_or_none()


async def get_or_create_category(db: AsyncSession, name: str) -> tuple[Category, bool]:
    """Retorna a categoria `name` (RF09), criando-a se ainda não existir.

    Comparação case-insensitive: `"Tecnologia"` e `"tecnologia"` resolvem
    para a mesma categoria — evita duplicatas quando o editor cadastra uma
    categoria "nova" que, na prática, já existe com capitalização diferente.
    Retorna `(categoria, criada)`; quem chama (o router) traduz `criada` em
    `201`/`200`.
    """

    existing = await get_category_by_name(db, name)
    if existing is not None:
        return existing, False

    category = Category(id=str(uuid.uuid4()), name=name)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category, True
