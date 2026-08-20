# sdd-blog-cms

> ⚠️ **Projeto de estudo/experimentação.** Não é um produto em produção nem
> destinado a uso real. Criado para aprender e testar, na prática,
> **Spec-Driven Development (SDD)** combinado com **Claude Code** e
> assistentes de IA no dia a dia de desenvolvimento — além de servir de
> laboratório para uma stack moderna de containers e orquestração.

## Objetivo do projeto

Este repositório é um CMS de blog (estilo WordPress) com um assistente de IA generativa para redigir rascunhos de posts. O software em si é secundário:
o real objetivo é validar, na prática, um fluxo de trabalho onde:

1. **Toda funcionalidade nasce como spec** em [`specs/features/`](specs/features/)
   antes de qualquer linha de código.
2. **Os testes são escritos a partir dos critérios de aceite da spec**, antes da implementação (TDD orientado por spec).
3. **O Claude Code conduz boa parte da implementação**, usando subagentes
   especializados e slash commands definidos em [`.claude/`](.claude/)
   (`backend-builder`, `frontend-builder`, `test-writer`, `spec-reviewer`,
   `ai-safety-reviewer`, entre outros).
4. **Nada de código órfão**: se não existe spec para algo, é tratado como
   débito técnico.

Ou seja — este projeto existe para responder à pergunta "como fica o
desenvolvimento quando a spec, o teste e o agente de IA fazem parte do
processo desde o início?", não para virar um CMS de verdade.

## O que dá para aprender aqui

- **Spec-Driven Development** — como estruturar specs (`specs/PRODUCT.md`,
  `specs/ARCHITECTURE.md`, `specs/TESTING.md`, `specs/features/SPEC-XXX-*.md`) e usá-las como fonte única de verdade para código e testes.
- **Claude Code na prática** — slash commands customizados, subagentes com
  ferramentas restritas por responsabilidade, e um revisor de segurança
  dedicado (`ai-safety-reviewer`) para qualquer código que chame uma LLM.
- **Integração com LLMs (Anthropic/Gemini)** — geração assíncrona de
  conteúdo via worker, prompt engineering, defesa contra prompt injection,
  validação de schema da saída do modelo e transparência de custo (uso de
  tokens exposto ao usuário).
- **Backend assíncrono em Python** — FastAPI + SQLAlchemy 2.x (async) +
  Alembic, com jobs de IA processados fora do request/response via
  Redis + worker.
- **Frontend moderno** — Next.js (App Router), React, TypeScript estrito e
  Tailwind CSS v4, com rotas públicas e administrativas separadas.
- **Containers e orquestração** — build de imagens Docker e deploy completo
  em Kubernetes (namespace, configmap, secret, StatefulSet para MySQL,
  Deployments para backend/worker/frontend, Service e Ingress — ver
  [`k8s/`](k8s/)).
- **Qualidade e CI** — testes unitários e de integração (pytest/testcontainers no backend, Vitest/RTL/MSW no frontend), cobertura mínima e pipeline no GitHub Actions.
- **Publicação de imagens e deploy em nuvem** — workflow do GitHub Actions
  (`.github/workflows/publish-images.yml`) faz build das imagens e publica
  tanto no Docker Hub quanto no Google Artifact Registry, autenticando no
  GCP via Workload Identity Federation (sem chave de service account). No
  GKE, a aplicação fica exposta por um Load Balancer nativo do Google Cloud
  (Ingress classe `gce`, ver [`k8s/09-ingress.yaml`](k8s/09-ingress.yaml)).

## Stack

| Camada          | Tecnologia                                                        |
|-----------------|--------------------------------------------------------------------|
| Backend         | Python 3.12 · FastAPI · SQLAlchemy 2.x (async) · Alembic            |
| IA generativa   | Anthropic Claude / Google Gemini (configurável), worker assíncrono  |
| Banco de dados  | MySQL 8                                                              |
| Fila / cache    | Redis + worker (jobs de geração de rascunho via IA)                 |
| Storage         | MinIO (S3-compatible) para imagens/mídia                            |
| Frontend        | Next.js (App Router) · React · TypeScript strict · Tailwind CSS v4  |
| Testes backend  | pytest · pytest-asyncio · httpx · pytest-cov · testcontainers       |
| Testes frontend | Vitest · React Testing Library · MSW                                |
| Containers      | Docker + Kubernetes (um Deployment/StatefulSet por componente)      |
| CI/CD           | GitHub Actions (build + push para Docker Hub e Google Artifact Registry) |
| Dev assistido   | Claude Code (subagentes, slash commands, SDD)                       |

## Estrutura

```
.
├── backend/          # API FastAPI + worker de IA
├── frontend/          # Next.js (blog público + área admin)
├── docker/            # Dockerfiles (backend/worker e frontend)
├── k8s/               # Manifests Kubernetes (kubectl apply -f k8s/)
├── specs/             # Especificações (produto, arquitetura, testes, features)
│   └── features/      # Uma spec por funcionalidade (SPEC-001, SPEC-002, ...)
└── .claude/           # Slash commands e subagentes do Claude Code
```

Detalhes de cada camada estão documentados em `CLAUDE.md` e em
`specs/ARCHITECTURE.md`.

## Rodando localmente

Requer um cluster Kubernetes local (kind, minikube ou Docker Desktop
Kubernetes):

```bash
# Build das imagens
docker build -f docker/backend.Dockerfile -t sdd-blog-cms-backend:local backend/
docker build -f docker/frontend.Dockerfile -t sdd-blog-cms-frontend:local frontend/
kind load docker-image sdd-blog-cms-backend:local sdd-blog-cms-frontend:local  # minikube: `minikube image load`

# Configuração (preencha os CHANGE_ME antes de aplicar — nunca commitar secret.yaml)
cp k8s/02-secret.example.yaml k8s/secret.yaml

# Deploy
kubectl apply -f k8s/00-namespace.yaml -f k8s/01-configmap.yaml -f k8s/secret.yaml \
  -f k8s/03-mysql.yaml -f k8s/04-redis.yaml -f k8s/05-minio.yaml \
  -f k8s/06-backend.yaml -f k8s/07-worker.yaml -f k8s/08-frontend.yaml -f k8s/09-ingress.yaml
```

Testes:

```bash
cd backend && pytest --cov=app tests/unit
cd frontend && npm run test
```

Mais comandos (migrations, etc.) em `CLAUDE.md`.

## Publicando imagens (Docker Hub + Google Cloud)

O workflow [`publish-images.yml`](.github/workflows/publish-images.yml) builda
backend e frontend e publica as imagens tanto no Docker Hub quanto no Google
Artifact Registry (autenticação no GCP via Workload Identity Federation,
sem chave de service account armazenada no repo). Dispara automaticamente ao
dar push numa tag `vX.Y.Z`, ou manualmente pela aba **Actions → Publish
images → Run workflow**.

## Fluxo SDD deste repositório

1. Nova funcionalidade → spec em `specs/features/SPEC-XXX-nome.md`
   (`/new-spec`).
2. Implementação → `/implement-spec`, que escreve testes a partir dos
   critérios de aceite e só então o código.
3. Todo teste referencia o ID da spec (ex.:
   `test_generate_draft_returns_title_spec003`).
4. Uma spec = um branch (`feat/SPEC-XXX-slug`) = um PR.
5. Auditoria de conformidade sob demanda via `/review-spec`.

## Licença / uso

Projeto pessoal de estudo. Sem garantias, sem suporte, não recomendado para
uso em produção.
