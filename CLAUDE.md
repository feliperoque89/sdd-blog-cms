# CLAUDE.md

Este arquivo é lido automaticamente pelo Claude Code no início de cada sessão.
Ele define contexto, convenções e regras do projeto. Sempre siga o fluxo SDD
descrito abaixo — nunca implemente uma funcionalidade sem uma spec aprovada em `specs/`.

## Visão geral do projeto

CMS de blog com assistente de IA generativa para redigir posts (estilo WordPress),
dividido em:
- **Backend restrito** (área administrativa): CRUD de posts, autenticação, geração
  de rascunhos via IA.
- **Frontend público** (blog): leitura dos posts publicados, SEO-friendly.

O objetivo principal deste projeto é validar **Spec-Driven Development (SDD)**:
toda funcionalidade nasce como spec em `specs/`, depois vira testes, depois vira
implementação. Código sem spec correspondente deve ser tratado como débito técnico.

## Stack tecnológica

| Camada         | Tecnologia                                              |
|----------------|----------------------------------------------------------|
| Backend        | Python 3.12 + FastAPI + SQLAlchemy 2.x (async) + Alembic |
| Banco de dados | MySQL 8                                                   |
| Fila / cache   | Redis + worker (Celery ou RQ) para jobs de IA assíncronos |
| Storage        | MinIO (S3-compatible) para mídia/imagens                  |
| Frontend       | Next.js (App Router) + React + TypeScript strict + Tailwind CSS v4 |
| Testes backend | pytest, pytest-asyncio, httpx, pytest-cov, testcontainers |
| Testes frontend| Vitest + React Testing Library + MSW                      |
| Containers     | Docker (build de imagem) + Kubernetes (orquestração — um Deployment/StatefulSet por componente, ver `k8s/`) |
| CI/CD          | GitHub Actions                                             |
| Versionamento  | GitHub, Conventional Commits, branch por spec              |

## Estrutura de pastas (monorepo)

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # routers FastAPI
│   │   ├── core/           # config, security, settings
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas (contratos)
│   │   ├── services/       # regra de negócio
│   │   └── workers/        # tasks assíncronas (IA)
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── alembic/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (public)/   # rotas do blog
│   │   │   └── (admin)/    # rotas restritas
│   │   ├── components/
│   │   └── lib/
│   └── tests/
├── docker/
│   ├── backend.Dockerfile     # imagem única usada por backend E worker (comando diferente)
│   └── frontend.Dockerfile
├── k8s/                        # manifests Kubernetes (namespace/configmap/secret/
│   │                            # statefulset/deployment/service/ingress), aplicados
│   │                            # com `kubectl apply -f k8s/` — ver "Comandos úteis"
│   └── ...
├── specs/
│   ├── PRODUCT.md
│   ├── ARCHITECTURE.md
│   ├── TESTING.md
│   └── features/
│       └── SPEC-XXX-nome-da-feature.md
└── .github/workflows/
```

## Fluxo SDD obrigatório

1. **Spec primeiro.** Nenhuma implementação começa sem um arquivo em
   `specs/features/SPEC-XXX-nome.md` aprovado (use o comando `/new-spec`).
2. **Teste antes do código.** Ao implementar uma spec (`/implement-spec`), escreva
   primeiro os testes unitários derivados dos critérios de aceite, depois o código
   que os satisfaz.
3. **Rastreabilidade.** Todo teste deve referenciar o ID da spec no nome ou no
   docstring, ex: `test_generate_draft_returns_title_spec003`.
4. **Uma spec = um branch = um PR.** Nome do branch: `feat/SPEC-XXX-slug`.
5. **Nada de código órfão.** Se o código não corresponde a nenhuma spec ativa,
   pare e pergunte antes de continuar.

## Convenções de código

### Backend (Python)
- Formatação: `black` + `ruff` (lint e imports).
- Tipagem obrigatória (type hints em tudo, `mypy` no CI).
- Toda rota FastAPI tem `response_model` explícito (Pydantic).
- Regra de negócio fica em `services/`, nunca direto no router.
- Nunca chamar a API de LLM real dentro de testes unitários — sempre mockar
  o client (ver `specs/TESTING.md`).
- Prompts de sistema para a IA ficam apenas no backend (`services/ai_assistant.py`
  ou similar) e nunca são expostos ao cliente.

### Frontend (TypeScript / Next.js)
- `strict: true` no `tsconfig.json`, sem `any` implícito.
- Server Components por padrão; `"use client"` só quando necessário
  (formulários, editor, streaming).
- Rotas do blog público em `app/(public)/...`, rotas administrativas em
  `app/(admin)/...`, protegidas por middleware.
- Tailwind v4: usar tokens/variáveis do tema, evitar valores mágicos inline.
- ESLint + Prettier obrigatórios, sem warnings no CI.

### Commits
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Referenciar a spec no corpo do commit: `Refs: SPEC-003`.

## Testes — regra geral

- Toda funcionalidade nova exige testes unitários antes do merge (ver
  `specs/TESTING.md` para detalhes de mocking, cobertura mínima e CI).
- Cobertura mínima: 80% em `backend/app` e `frontend/src`.
- Testes de integração com banco real rodam via `testcontainers`, isolados dos
  testes unitários.

## Comandos úteis

```bash
# Subir tudo num cluster local (kind/minikube/Docker Desktop Kubernetes)
docker build -f docker/backend.Dockerfile -t sdd-blog-cms-backend:local backend/
docker build -f docker/frontend.Dockerfile -t sdd-blog-cms-frontend:local frontend/
kind load docker-image sdd-blog-cms-backend:local sdd-blog-cms-frontend:local  # só em kind; minikube usa `minikube image load`
cp k8s/02-secret.example.yaml k8s/secret.yaml   # preencha os CHANGE_ME antes de aplicar (nunca commitar)
kubectl apply -f k8s/00-namespace.yaml -f k8s/01-configmap.yaml -f k8s/secret.yaml \
  -f k8s/03-mysql.yaml -f k8s/04-redis.yaml -f k8s/05-minio.yaml \
  -f k8s/06-backend.yaml -f k8s/07-worker.yaml -f k8s/08-frontend.yaml -f k8s/09-ingress.yaml

# Backend - testes
cd backend && pytest --cov=app tests/unit

# Frontend - testes
cd frontend && npm run test

# Migrations (local, contra o DATABASE_URL do .env; em cluster, rode via
# `kubectl exec deploy/backend -n sdd-blog-cms -- alembic upgrade head`)
cd backend && alembic upgrade head
```

## Slash commands disponíveis (`.claude/commands/`)

- `/new-spec <nome da feature>` — cria uma nova spec seguindo o template padrão.
- `/implement-spec <caminho da spec>` — implementa uma spec seguindo TDD.
- `/write-tests <caminho ou spec>` — gera/completa testes unitários faltantes.
- `/review-spec <caminho da spec>` — audita se a implementação atual cumpre a spec.

## Subagentes disponíveis (`.claude/agents/`)

Cada subagente roda em contexto isolado, com ferramentas restritas ao seu
papel. Os slash commands acima já delegam a eles automaticamente — mas
também podem ser chamados diretamente (`@backend-builder`, ou "use o
subagente X para...").

- `backend-builder` — implementa código em `backend/` (nunca toca em `frontend/`).
- `frontend-builder` — implementa código em `frontend/` (nunca toca em `backend/`).
- `test-writer` — escreve testes unitários a partir dos critérios de aceite de uma spec.
- `spec-reviewer` — auditoria somente leitura de código vs. spec.
- `ai-safety-reviewer` — revisor somente leitura especializado em prompt
  injection, vazamento de system prompt e validação de saída, obrigatório
  para qualquer feature que chame a LLM.

Regra: qualquer feature que envolva chamada à LLM só é considerada
`Implementado` depois de passar pelo `ai-safety-reviewer` sem achados
críticos.
