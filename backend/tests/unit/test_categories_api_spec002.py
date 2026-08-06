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


async def test_post_categories_creates_new_category_spec002(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.post("/api/admin/categories", json={"name": "Tecnologia"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Tecnologia"
    assert body["id"]


async def test_post_categories_returns_existing_category_case_insensitively_spec002(
    editor_client: AsyncClient,
) -> None:
    created = await editor_client.post("/api/admin/categories", json={"name": "Tecnologia"})
    created_id = created.json()["id"]

    response = await editor_client.post("/api/admin/categories", json={"name": "  tecnologia  "})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created_id
    assert body["name"] == "Tecnologia"

    listing = await editor_client.get("/api/admin/categories")
    assert len([c for c in listing.json() if c["id"] == created_id]) == 1


async def test_post_categories_requires_non_empty_name_spec002(
    editor_client: AsyncClient,
) -> None:
    missing = await editor_client.post("/api/admin/categories", json={})
    assert missing.status_code == 422

    blank = await editor_client.post("/api/admin/categories", json={"name": "   "})
    assert blank.status_code == 422


async def test_post_categories_without_authentication_returns_401_spec002(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/admin/categories", json={"name": "Tecnologia"})

    assert response.status_code == 401
