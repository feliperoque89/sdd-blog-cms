# PRODUCT.md — Visão de Produto

## Status
Ativo

## Objetivo
Construir um CMS de blog simples, com uma área administrativa restrita para
gestão de conteúdo e um blog público performático, incluindo um assistente de
IA generativa que ajuda o editor a redigir rascunhos de posts.

## Personas

| Persona | Descrição |
|---|---|
| **Admin** | Gerencia usuários, categorias e configurações gerais. |
| **Editor** | Cria, edita e publica posts; usa o assistente de IA para gerar rascunhos. |
| **Leitor** | Acessa o blog público, lê posts publicados, sem autenticação. |

## Escopo do MVP

1. Autenticação de Admin/Editor (login, sessão via JWT em cookie httpOnly).
2. CRUD de posts (rascunho, publicado, agendado — opcional na v1).
3. CRUD de categorias/tags.
4. Assistente de IA: gera rascunho de post (título, corpo em markdown, meta
   description, tags sugeridas) a partir de um tópico/instrução do editor.
5. Blog público: listagem paginada, página de post individual, busca simples
   por título, SEO básico (meta tags, sitemap).
6. Upload de imagem de capa (armazenada via MinIO).

## Fora de escopo (v1)

- Comentários de leitores.
- Multi-idioma.
- Múltiplos sites/instâncias (multi-tenant).
- Editor colaborativo em tempo real.
- Geração de imagens via IA (só texto na v1).

## Glossário

- **Draft**: post não publicado, visível apenas na área admin.
- **Assistant Draft**: rascunho gerado pela IA, que o editor revisa antes de
  salvar como Draft ou publicar.
- **Published**: post visível no blog público.

## Métricas de sucesso do experimento SDD

- Toda feature implementada possui spec correspondente rastreável.
- Cobertura de testes unitários ≥ 80% desde o primeiro PR de cada feature.
- Nenhum PR mesclado sem testes referenciando a spec.
