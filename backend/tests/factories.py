"""Factories de dados de teste (factory_boy), conforme specs/TESTING.md.

Contrato assumido para o backend-builder (ainda não implementado):

- `app.models.user.User`: modelo SQLAlchemy com, no mínimo, os campos
  `id: str` (UUID), `name: str`, `email: str` (único), `hashed_password: str`
  e `role: UserRole`.
- `app.models.user.UserRole`: `Enum` (`str`, `Enum`) com os membros `ADMIN`
  ("admin") e `EDITOR` ("editor"), espelhando o contrato de
  `specs/features/SPEC-001-auth.md` (`"role": "admin" | "editor"`).
- `app.core.security.hash_password(plain: str) -> str`: hashing de senha
  (bcrypt/argon2, RNF01), usado aqui para popular `hashed_password` com um
  hash válido a partir de `DEFAULT_RAW_PASSWORD`.

`UserFactory` usa `factory.Factory` (não `SQLAlchemyModelFactory`) de
propósito: apenas constrói a instância em memória (`.build()`), a
persistência em banco (SQLite in-memory) fica a cargo dos fixtures em
`conftest.py`, que fazem `session.add()` / `session.commit()` explicitamente
— isso evita acoplar a factory a uma sessão async específica.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import factory

from app.core.security import hash_password
from app.models.user import User, UserRole

# Senha "correta" padrão usada pelos testes ao criar usuários via factory.
# Mantida em um único lugar para evitar strings mágicas espalhadas pelos
# testes (ver backend/tests/unit/test_auth_service_spec001.py).
DEFAULT_RAW_PASSWORD = "Str0ng!Passw0rd123"


class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"Usuária de Teste {n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    role = UserRole.EDITOR
    is_active = True
    hashed_password = factory.LazyFunction(lambda: hash_password(DEFAULT_RAW_PASSWORD))


# ---------------------------------------------------------------------------
# SPEC-002 (CRUD de posts) — `app.models.category`/`app.models.post` ainda
# não existem (fase RED do TDD, ver `tests/unit/test_posts_service_spec002.py`).
#
# O `try/except` abaixo é proposital: garante que este módulo continua
# importável (e `UserFactory` continua utilizável pelos testes de SPEC-001,
# já implementada) mesmo antes do backend-builder criar
# `app.models.category`/`app.models.post`. Só depois que esses módulos
# existirem é que `CategoryFactory`/`PostFactory` passam a ser definidas; até
# lá, `from tests.factories import CategoryFactory` (feito pelo teste de
# SPEC-002) falha com `ImportError` — exatamente o RED esperado, isolado do
# restante da suíte.
# ---------------------------------------------------------------------------
try:
    from app.models.category import Category
    from app.models.post import Post, PostStatus
except ImportError:  # pragma: no cover - só ocorre antes da SPEC-002 (fase RED)
    Category = None  # type: ignore[assignment, misc]
    Post = None  # type: ignore[assignment, misc]
    PostStatus = None  # type: ignore[assignment, misc]
else:

    class CategoryFactory(factory.Factory):
        """Factory de `app.models.category.Category` (SPEC-002)."""

        class Meta:
            model = Category

        id = factory.LazyFunction(lambda: str(uuid.uuid4()))
        name = factory.Sequence(lambda n: f"Categoria de Teste {n}")

    class PostFactory(factory.Factory):
        """Factory de `app.models.post.Post` (SPEC-002).

        Construída via `.build()` (não persiste sozinha — quem chama decide
        `session.add()`/`commit()`), igual ao padrão de `UserFactory`. Usada
        nos testes para semear posts diretamente no banco (sem passar pela
        API), quando o teste precisa de dados determinísticos (ex.: vários
        posts com `published_at` espaçados, para o teste de paginação).
        """

        class Meta:
            model = Post

        id = factory.LazyFunction(lambda: str(uuid.uuid4()))
        title = factory.Sequence(lambda n: f"Post de Teste {n}")
        slug = factory.Sequence(lambda n: f"post-de-teste-{n}")
        content_markdown = "# Título\n\nConteúdo de exemplo para testes."
        category_id = None
        cover_image_url = None
        status = PostStatus.PUBLISHED
        deleted_at = None
        published_at = factory.LazyFunction(lambda: datetime.now(UTC))
        created_at = factory.LazyFunction(lambda: datetime.now(UTC))
