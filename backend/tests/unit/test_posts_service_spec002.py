"""Testes unitários — SPEC-002 (CRUD de Posts).

Fonte: specs/features/SPEC-002-posts-crud.md
Depende de SPEC-001 (autenticação), já implementada — reaproveita `client`,
`seed_editor_user`, `seed_admin_user` e as novas fixtures `editor_client`/
`admin_client` de `tests/conftest.py`.

Fase RED do TDD: `app.models.post`, `app.models.category`,
`app.schemas.post`, `app.services.post_service`, `app.api.posts_admin` e
`app.api.posts_public` ainda não existem. A simples importação de
`app.models.category`/`app.models.post` abaixo já é suficiente para que
`pytest` reporte um erro de coleta (`ModuleNotFoundError`) neste arquivo —
esse é o comportamento esperado até o backend-builder implementar a spec.
Nenhum outro arquivo de teste é afetado (ver nota em `tests/factories.py`).

Mapeamento critério de aceite -> teste:
1. Título "Como usar SDD" -> slug "como-usar-sdd"
   -> test_create_post_generates_slug_from_title_spec002
2. Slug já existente -> sufixo numérico ("como-usar-sdd-2")
   -> test_create_post_with_duplicate_title_appends_numeric_suffix_to_slug_spec002
   -> test_create_post_with_third_duplicate_title_uses_incrementing_slug_suffix_spec002
3. Post `draft` -> `GET /api/posts/{slug}` público retorna 404
   -> test_public_get_post_by_slug_returns_404_when_post_is_draft_spec002
4. Soft delete -> some da listagem admin por padrão, mas aparece com
   `include_deleted=true`
   -> test_soft_deleted_post_excluded_from_admin_listing_by_default_spec002
   -> test_soft_deleted_post_appears_in_admin_listing_with_include_deleted_true_spec002
5. Listagem pública, página 2 com page_size=10 -> itens 11-20 por data desc.
   -> test_public_listing_page_2_returns_items_11_to_20_ordered_by_published_at_desc_spec002

Casos de teste obrigatórios (todos mapeados abaixo, ver seções comentadas):
- Criação de post com geração de slug (único e com colisão) -> critério 1/2.
- Edição altera apenas os campos enviados
  -> test_update_post_changes_only_sent_fields_spec002
  -> test_update_post_status_only_changes_status_and_keeps_other_fields_spec002
- Soft delete não aparece em listagens públicas nem admin por padrão
  -> test_soft_deleted_post_excluded_from_public_listing_spec002
  -> test_soft_deleted_post_excluded_from_admin_listing_by_default_spec002
- Post `draft` não é acessível publicamente (404) -> critério 3.
- Paginação retorna os itens corretos e metadados (total, página atual)
  -> test_public_listing_page_2_returns_items_11_to_20_ordered_by_published_at_desc_spec002
  -> test_public_listing_returns_pagination_metadata_spec002
- Usuário sem autenticação não consegue criar/editar/excluir (401/403)
  -> test_create_post_without_authentication_returns_401_spec002
  -> test_update_post_without_authentication_returns_401_spec002
  -> test_delete_post_without_authentication_returns_401_spec002
  -> test_admin_listing_without_authentication_returns_401_spec002

Contratos assumidos (a spec não define o schema JSON exato de paginação nem
o status HTTP de alguns casos de borda; documentado aqui, análogo à nota de
`RATE_LIMIT_STATUS_CODE` em `test_auth_service_spec001.py`, para o
backend-builder confirmar/ajustar):

- Envelope de listagem paginada (`GET /api/posts` e `GET /api/admin/posts`):
    { "items": [...], "total": <int>, "page": <int>, "page_size": <int> }
- RNF02 (page_size padrão 10, máximo 50): acima de 50 assumimos `422`
  (validação de query param, ex.: `Query(..., le=50)` no FastAPI).
- RF05 (RBAC): como só existem os papéis `editor`/`admin` (SPEC-001) e
  ambos têm permissão nas rotas `/api/admin/posts*`, não há cenário de `403`
  alcançável hoje para um usuário autenticado nessas rotas — só cobrimos o
  `401` (sem autenticação / token expirado), e confirmamos que os dois
  papéis (`editor` e `admin`) TÊM permissão (nenhum é bloqueado
  indevidamente).
- `PUT /api/admin/posts/{id}` e `DELETE /api/admin/posts/{id}` para um `id`
  inexistente: assumimos `404` (padrão REST).
- RNF01 (cache-control na listagem pública): só verificamos a presença do
  cabeçalho, não seu valor exato (não especificado pela spec).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient

from app.core import security
from app.models.category import Category
from app.models.post import Post, PostStatus
from tests.factories import CategoryFactory, PostFactory

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Helpers / fixtures locais
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def seed_category(db_session) -> Category:
    category = CategoryFactory.build()
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


async def _seed_post(
    db_session,
    category: Category,
    *,
    slug: str,
    status: PostStatus = PostStatus.PUBLISHED,
    title: str | None = None,
    published_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> Post:
    """Semeia um post diretamente no banco (sem passar pela API/serviço).

    Usado para cenários que precisam de dados determinísticos (ex.:
    `published_at` espaçados para o teste de paginação) sem depender da
    lógica de geração de slug do serviço, que é testada separadamente via
    `POST /api/admin/posts`.
    """

    post = PostFactory.build(
        category_id=category.id,
        slug=slug,
        title=title or slug,
        status=status,
        published_at=published_at if published_at is not None else datetime.now(UTC),
        deleted_at=deleted_at,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


def _post_payload(
    *,
    category_id: str,
    title: str = "Como usar SDD",
    content_markdown: str = "# Como usar SDD\n\nConteúdo de exemplo.",
    tags: list[str] | None = None,
    cover_image_url: str | None = None,
    status: str = "draft",
) -> dict[str, object]:
    return {
        "title": title,
        "content_markdown": content_markdown,
        "category_id": category_id,
        "tags": tags if tags is not None else [],
        "cover_image_url": cover_image_url,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Critério de aceite 1 / caso obrigatório "Criação de post com geração de
# slug"
# ---------------------------------------------------------------------------
async def test_create_post_generates_slug_from_title_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    payload = _post_payload(title="Como usar SDD", category_id=seed_category.id)

    response = await editor_client.post("/api/admin/posts", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Como usar SDD"
    assert body["slug"] == "como-usar-sdd"


# ---------------------------------------------------------------------------
# Critério de aceite 2 / caso obrigatório "... e com colisão"
# ---------------------------------------------------------------------------
async def test_create_post_with_duplicate_title_appends_numeric_suffix_to_slug_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    payload = _post_payload(title="Como usar SDD", category_id=seed_category.id)

    first = await editor_client.post("/api/admin/posts", json=payload)
    second = await editor_client.post("/api/admin/posts", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["slug"] == "como-usar-sdd"
    assert second.json()["slug"] == "como-usar-sdd-2"


async def test_create_post_with_third_duplicate_title_uses_incrementing_slug_suffix_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    payload = _post_payload(title="Como usar SDD", category_id=seed_category.id)

    slugs = []
    for _ in range(3):
        response = await editor_client.post("/api/admin/posts", json=payload)
        assert response.status_code == 201
        slugs.append(response.json()["slug"])

    assert slugs == ["como-usar-sdd", "como-usar-sdd-2", "como-usar-sdd-3"]


# ---------------------------------------------------------------------------
# Critério de aceite 3 — post `draft` não é acessível publicamente (404),
# complementado pelo caminho de sucesso (post publicado -> 200) e pelo caso
# de slug inexistente (-> 404), exigidos por "O que sempre precisa de teste"
# (specs/TESTING.md).
# ---------------------------------------------------------------------------
async def test_public_get_post_by_slug_returns_404_when_post_is_draft_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    draft_post = await _seed_post(
        db_session, seed_category, slug="post-rascunho", status=PostStatus.DRAFT
    )

    response = await client.get(f"/api/posts/{draft_post.slug}")

    assert response.status_code == 404


async def test_public_get_post_by_slug_returns_200_when_post_is_published_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    published_post = await _seed_post(
        db_session, seed_category, slug="post-publicado", status=PostStatus.PUBLISHED
    )

    response = await client.get(f"/api/posts/{published_post.slug}")

    assert response.status_code == 200
    assert response.json()["slug"] == "post-publicado"


async def test_public_get_post_by_slug_returns_404_when_slug_does_not_exist_spec002(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/posts/slug-que-nao-existe")

    assert response.status_code == 404


async def test_public_listing_only_returns_published_posts_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    await _seed_post(
        db_session, seed_category, slug="rascunho-nao-listado", status=PostStatus.DRAFT
    )
    await _seed_post(
        db_session, seed_category, slug="publicado-listado", status=PostStatus.PUBLISHED
    )

    response = await client.get("/api/posts")

    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()["items"]]
    assert "publicado-listado" in slugs
    assert "rascunho-nao-listado" not in slugs


# ---------------------------------------------------------------------------
# Critério de aceite 4 / caso obrigatório "Soft delete não aparece em
# listagens públicas nem admin por padrão"
# ---------------------------------------------------------------------------
async def test_delete_post_soft_deletes_and_returns_204_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(category_id=seed_category.id, status="published"),
    )
    post_id = create_response.json()["id"]

    delete_response = await editor_client.delete(f"/api/admin/posts/{post_id}")

    assert delete_response.status_code == 204


async def test_soft_deleted_post_excluded_from_public_listing_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Post que será excluído", category_id=seed_category.id, status="published"
        ),
    )
    post = create_response.json()
    await editor_client.delete(f"/api/admin/posts/{post['id']}")

    listing = await editor_client.get("/api/posts")

    slugs = [item["slug"] for item in listing.json()["items"]]
    assert post["slug"] not in slugs


async def test_soft_deleted_post_returns_404_on_public_detail_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Outro post excluído", category_id=seed_category.id, status="published"
        ),
    )
    post = create_response.json()
    await editor_client.delete(f"/api/admin/posts/{post['id']}")

    detail_response = await editor_client.get(f"/api/posts/{post['slug']}")

    assert detail_response.status_code == 404


async def test_soft_deleted_post_excluded_from_admin_listing_by_default_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Post admin excluído", category_id=seed_category.id, status="published"
        ),
    )
    post = create_response.json()
    await editor_client.delete(f"/api/admin/posts/{post['id']}")

    listing = await editor_client.get("/api/admin/posts")

    ids = [item["id"] for item in listing.json()["items"]]
    assert post["id"] not in ids


async def test_soft_deleted_post_appears_in_admin_listing_with_include_deleted_true_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Post admin com include_deleted", category_id=seed_category.id, status="published"
        ),
    )
    post = create_response.json()
    await editor_client.delete(f"/api/admin/posts/{post['id']}")

    listing = await editor_client.get("/api/admin/posts", params={"include_deleted": "true"})

    items_by_id = {item["id"]: item for item in listing.json()["items"]}
    assert post["id"] in items_by_id
    assert items_by_id[post["id"]]["deleted_at"] is not None


# ---------------------------------------------------------------------------
# Critério de aceite 5 / caso obrigatório "Paginação retorna os itens
# corretos e metadados (total, página atual)"
# ---------------------------------------------------------------------------
async def test_public_listing_page_2_returns_items_11_to_20_ordered_by_published_at_desc_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    total_posts = 25
    for i in range(total_posts):
        await _seed_post(
            db_session,
            seed_category,
            slug=f"post-{i:02d}",
            status=PostStatus.PUBLISHED,
            published_at=base_time + timedelta(minutes=i),
        )

    response = await client.get("/api/posts", params={"page": 2, "page_size": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["total"] == total_posts

    # Mais recente (maior published_at) primeiro. Página 1 = ranks 1-10 (i=24..15),
    # página 2 = ranks 11-20 (i=14..5).
    expected_slugs = [f"post-{i:02d}" for i in range(14, 4, -1)]
    returned_slugs = [item["slug"] for item in body["items"]]
    assert returned_slugs == expected_slugs


async def test_public_listing_returns_pagination_metadata_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    for i in range(15):
        await _seed_post(db_session, seed_category, slug=f"meta-post-{i:02d}")

    response = await client.get("/api/posts")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 15
    assert body["page"] == 1
    assert body["page_size"] == DEFAULT_PAGE_SIZE
    assert len(body["items"]) == DEFAULT_PAGE_SIZE


async def test_public_listing_page_size_above_max_returns_422_spec002(client: AsyncClient) -> None:
    response = await client.get("/api/posts", params={"page_size": MAX_PAGE_SIZE + 1})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Caso obrigatório "Edição de post altera apenas os campos enviados"
# ---------------------------------------------------------------------------
async def test_update_post_changes_only_sent_fields_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Título original",
            content_markdown="Conteúdo original",
            category_id=seed_category.id,
            cover_image_url="https://cdn.example.com/original.png",
            status="draft",
        ),
    )
    post = create_response.json()

    update_response = await editor_client.put(
        f"/api/admin/posts/{post['id']}", json={"title": "Título atualizado"}
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Título atualizado"
    # Campos não enviados no PUT permanecem inalterados.
    assert updated["content_markdown"] == "Conteúdo original"
    assert updated["category_id"] == seed_category.id
    assert updated["cover_image_url"] == "https://cdn.example.com/original.png"
    assert updated["status"] == "draft"


async def test_update_post_status_only_changes_status_and_keeps_other_fields_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    create_response = await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Post ainda rascunho", category_id=seed_category.id, status="draft"
        ),
    )
    post = create_response.json()

    update_response = await editor_client.put(
        f"/api/admin/posts/{post['id']}", json={"status": "published"}
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "published"
    assert updated["title"] == post["title"]
    assert updated["content_markdown"] == post["content_markdown"]

    # RF03 + RF07: publicar via PUT deve tornar o post visível no endpoint
    # público imediatamente.
    public_response = await editor_client.get(f"/api/posts/{post['slug']}")
    assert public_response.status_code == 200


async def test_update_nonexistent_post_returns_404_spec002(editor_client: AsyncClient) -> None:
    response = await editor_client.put(
        "/api/admin/posts/id-que-nao-existe", json={"title": "Não importa"}
    )

    assert response.status_code == 404


async def test_delete_nonexistent_post_returns_404_spec002(editor_client: AsyncClient) -> None:
    response = await editor_client.delete("/api/admin/posts/id-que-nao-existe")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Caso obrigatório "Usuário sem autenticação não consegue criar/editar/
# excluir (401/403)"
# ---------------------------------------------------------------------------
async def test_create_post_without_authentication_returns_401_spec002(
    client: AsyncClient, seed_category: Category
) -> None:
    response = await client.post(
        "/api/admin/posts", json=_post_payload(category_id=seed_category.id)
    )

    assert response.status_code == 401


async def test_update_post_without_authentication_returns_401_spec002(client: AsyncClient) -> None:
    response = await client.put(
        "/api/admin/posts/algum-id", json={"title": "Tentativa não autenticada"}
    )

    assert response.status_code == 401


async def test_delete_post_without_authentication_returns_401_spec002(client: AsyncClient) -> None:
    response = await client.delete("/api/admin/posts/algum-id")

    assert response.status_code == 401


async def test_admin_listing_without_authentication_returns_401_spec002(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/admin/posts")

    assert response.status_code == 401


async def test_create_post_with_expired_token_returns_401_spec002(
    client: AsyncClient, seed_editor_user, seed_category: Category
) -> None:
    user, _raw_password = seed_editor_user
    expired_access_token = security.create_access_token(
        data={"sub": user.id, "role": user.role, "type": "access"},
        expires_delta=timedelta(minutes=-5),
    )
    client.cookies.set("access_token", expired_access_token)

    response = await client.post(
        "/api/admin/posts", json=_post_payload(category_id=seed_category.id)
    )

    assert response.status_code == 401


# RF01/RF03 permitem tanto `editor` quanto `admin` nas rotas administrativas
# de posts (SPEC-002 não distingue os dois papéis, diferente de SPEC-001);
# confirmamos que nenhum dos dois é indevidamente bloqueado.
async def test_editor_role_can_create_post_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    response = await editor_client.post(
        "/api/admin/posts", json=_post_payload(category_id=seed_category.id)
    )

    assert response.status_code == 201


async def test_admin_role_can_create_post_spec002(
    admin_client: AsyncClient, seed_category: Category
) -> None:
    response = await admin_client.post(
        "/api/admin/posts", json=_post_payload(category_id=seed_category.id)
    )

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Validação de payload (RF01) — "O que sempre precisa de teste" / TESTING.md.
# ---------------------------------------------------------------------------
async def test_create_post_missing_required_fields_returns_422_spec002(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.post("/api/admin/posts", json={"tags": ["incompleto"]})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# RF05 — filtros da listagem admin (status, categoria, busca por título).
# ---------------------------------------------------------------------------
async def test_admin_listing_filters_by_status_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(title="Rascunho A", category_id=seed_category.id, status="draft"),
    )
    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(title="Publicado A", category_id=seed_category.id, status="published"),
    )

    response = await editor_client.get("/api/admin/posts", params={"status": "draft"})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Rascunho A" in titles
    assert "Publicado A" not in titles


async def test_admin_listing_filters_by_search_query_spec002(
    editor_client: AsyncClient, seed_category: Category
) -> None:
    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Guia completo de FastAPI", category_id=seed_category.id, status="draft"
        ),
    )
    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(
            title="Receita de bolo de cenoura", category_id=seed_category.id, status="draft"
        ),
    )

    response = await editor_client.get("/api/admin/posts", params={"q": "FastAPI"})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Guia completo de FastAPI"]


async def test_admin_listing_filters_by_category_spec002(
    editor_client: AsyncClient, db_session
) -> None:
    category_a = CategoryFactory.build(name="Categoria A")
    category_b = CategoryFactory.build(name="Categoria B")
    db_session.add_all([category_a, category_b])
    await db_session.commit()

    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(title="Post da categoria A", category_id=category_a.id, status="draft"),
    )
    await editor_client.post(
        "/api/admin/posts",
        json=_post_payload(title="Post da categoria B", category_id=category_b.id, status="draft"),
    )

    response = await editor_client.get("/api/admin/posts", params={"category": category_a.id})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Post da categoria A"]


# ---------------------------------------------------------------------------
# RNF01 — listagem pública deve ser cacheável (só verificamos a presença do
# cabeçalho; o valor exato de `Cache-Control` não é definido pela spec).
# ---------------------------------------------------------------------------
async def test_public_listing_response_has_cache_control_header_spec002(
    client: AsyncClient, db_session, seed_category: Category
) -> None:
    await _seed_post(db_session, seed_category, slug="post-cache")

    response = await client.get("/api/posts")

    assert response.status_code == 200
    # `httpx.Headers` faz lookup case-insensitive por padrão.
    assert "cache-control" in response.headers
