"""Modelos SQLAlchemy (mapeamento ORM).

Importa todos os módulos de modelo pelo efeito colateral de registro em
`Base.metadata` (mesmo motivo documentado em `alembic/env.py`): um `Post`
referencia `categories.id` via `ForeignKey` como string, e o SQLAlchemy só
resolve essa referência no primeiro flush, contra as tabelas já registradas
em `Base.metadata` até aquele ponto. Sem este import, rodar o backend de
verdade (fora dos testes, que importam `Category`/`User`/etc. diretamente
via fixtures) fazia `POST /api/admin/posts` falhar com
`NoReferencedTableError: ... could not find table 'categories'`. Se um novo
módulo de modelo for criado, adicione o import aqui também.
"""

from app.models import ai_settings, assistant_draft, category, post, user  # noqa: F401
