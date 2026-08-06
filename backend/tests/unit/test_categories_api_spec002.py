"""Testes unitários — `GET /api/admin/categories` (SPEC-002 / RF01).

Endpoint adicionado para que o `PostEditor` (frontend) ofereça um seletor de
categorias existentes em vez de um campo de texto livre para `category_id`
— sem uma categoria válida, `POST /api/admin/posts` sempre falhava com
violação de chave estrangeira (post não salvava).
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.factories import CategoryFactory


async def test_list_categories_returns_seeded_categories_ordered_by_name_spec002(
    editor_client: AsyncClient, db_session
) -> None:
    category_b = CategoryFactory.build(name="Zebra")
    category_a = CategoryFactory.build(name="Abacaxi")
    db_session.add_all([category_b, category_a])
    await db_session.commit()

    response = await editor_client.get("/api/admin/categories")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["Abacaxi", "Zebra"]


async def test_list_categories_without_authentication_returns_401_spec002(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/admin/categories")

    assert response.status_code == 401


async def test_admin_role_can_list_categories_spec002(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/api/admin/categories")

    assert response.status_code == 200
