# SPEC-002 — CRUD de Posts

## Status
Implementado

## Objetivo
Permitir que Editor/Admin criem, editem, listem, excluam e publiquem posts,
e que Leitores vejam apenas os posts publicados no blog público.

## Contexto
Depende de SPEC-001 (autenticação) para todas as rotas administrativas.

## Requisitos funcionais

- RF01: Criar post com título, corpo (markdown), categoria, tags, imagem de
  capa (opcional) e status (`draft` | `published`).
- RF02: Slug gerado automaticamente a partir do título (único, com sufixo
  numérico em caso de colisão).
- RF03: Editar post existente (qualquer campo, inclusive status).
- RF04: Excluir post (soft delete — campo `deleted_at`).
- RF05: Listar posts na área admin com filtro por status, categoria e busca
  por título, paginado.
- RF06: Endpoint público lista apenas posts com status `published` e
  `deleted_at IS NULL`, ordenados por data de publicação decrescente.
- RF07: Endpoint público retorna um post por slug.

## Requisitos não funcionais

- RNF01: Resposta da listagem pública cacheável (cache-control apropriado).
- RNF02: Paginação obrigatória em qualquer listagem (limite padrão 10, máx 50).

## Contrato de API

### `POST /api/admin/posts` (auth: editor|admin)
Request:
```json
{
  "title": "string",
  "content_markdown": "string",
  "category_id": "uuid",
  "tags": ["string"],
  "cover_image_url": "string | null",
  "status": "draft" | "published"
}
```
Response `201`: objeto do post criado, incluindo `slug` gerado.

### `PUT /api/admin/posts/{id}` (auth: editor|admin)
Mesmo corpo do POST (campos parciais permitidos). Response `200`.

### `DELETE /api/admin/posts/{id}` (auth: editor|admin)
Response `204`. Soft delete.

### `GET /api/admin/posts?status=&category=&q=&page=&page_size=`
Response `200`: lista paginada, todos os status.

### `GET /api/posts?page=&page_size=` (público)
Response `200`: lista paginada, apenas `published`.

### `GET /api/posts/{slug}` (público)
Response `200`: post publicado. `404` se não existir ou não estiver publicado.

## Critérios de aceite

1. **Dado** um título "Como usar SDD", **quando** o post é criado, **então**
   o slug gerado é `como-usar-sdd`.
2. **Dado** um slug já existente, **quando** outro post usa o mesmo título,
   **então** o novo slug recebe sufixo (`como-usar-sdd-2`).
3. **Dado** um post com status `draft`, **quando** um leitor acessa
   `GET /api/posts/{slug}`, **então** recebe `404`.
4. **Dado** um post excluído (soft delete), **quando** listado na área admin
   sem filtro, **então** não aparece por padrão (a menos que filtro
   `include_deleted=true` seja passado).
5. **Dado** uma listagem pública, **quando** requisitada a página 2 com
   `page_size=10`, **então** retorna os posts de 11 a 20 ordenados por data.

## Casos de teste obrigatórios

- Criação de post com geração de slug (único e com colisão).
- Edição de post altera apenas os campos enviados.
- Soft delete não aparece em listagens públicas nem admin por padrão.
- Post `draft` não é acessível publicamente (404).
- Paginação retorna os itens corretos e metadados (total, página atual).
- Usuário sem autenticação não consegue criar/editar/excluir (401/403).

## Fora de escopo
- Versionamento de revisões do post.
- Agendamento de publicação (`scheduled_at`) — considerar em spec futura.
