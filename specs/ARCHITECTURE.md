# ARCHITECTURE.md — Arquitetura Técnica

## Status
Ativo

## Visão geral do cluster Kubernetes

Todos os recursos vivem no namespace `sdd-blog-cms` (`k8s/00-namespace.yaml`).
Manifests completos, um arquivo por componente, numerados na ordem de
aplicação (`k8s/00-namespace.yaml` … `k8s/09-ingress.yaml`).

```
                        ┌───────────────────────────┐
                        │  Ingress (ingress-nginx)    │
                        │  host: blog.local            │
                        └───────────────┬───────────────┘
                    ┌───────────────────┼────────────────────┐
                    │ path: /                     path: /api  │
          ┌─────────▼─────────┐          ┌──────────▼──────────┐
          │ Service: frontend    │          │ Service: backend      │
          │ Deployment (2 pods)   │          │ Deployment (2 pods)    │
          │   /  e /admin           │          │   /api/*                 │
          └───────────────────────┘          └───────────┬──────────────┘
                                                            │
                        ┌────────────────────────────────────┼─────────────────────────┐
                        │                                    │                          │
                ┌───────▼────────┐              ┌────────────▼─────────┐   ┌────────────▼───────┐
                │ StatefulSet:      │              │ Deployment: redis       │   │ Deployment: minio     │
                │ mysql + PVC        │              │ + PVC (fila/cache)       │   │ + PVC (mídia/imagens)  │
                │ (dados posts)       │              └────────────┬─────────────┘   └─────────────────────────┘
                └─────────────────────┘                            │
                                                          ┌─────────▼──────────┐
                                                          │ Deployment: worker     │
                                                          │ (loop de polling,        │
                                                          │  chama API da LLM)         │
                                                          └───────────────────────────┘
```

## Componentes Kubernetes

| Componente | Recursos                                   | Imagem base (build via `docker/`) | Porta       | Réplicas | Responsabilidade |
|------------|---------------------------------------------|------------------------------------|-------------|----------|-------------------|
| frontend   | `Deployment` + `Service`                     | node:20-alpine                     | 3000        | 2        | Next.js App Router |
| backend    | `Deployment` + `Service`                     | python:3.12-slim                   | 8000        | 2        | API REST FastAPI |
| worker     | `Deployment` (sem `Service`)                 | python:3.12-slim (mesma imagem do backend, comando diferente) | —           | 1        | Consome a fila Redis, chama a API da LLM |
| mysql      | `StatefulSet` + `Service` headless + `PVC`   | mysql:8                            | 3306        | 1        | Persistência |
| redis      | `Deployment` + `Service` + `PVC`             | redis:7-alpine                     | 6379        | 1        | Fila (`BLPOP`) + cache |
| minio      | `Deployment` + `Service` + `PVC`             | minio/minio                        | 9000/9001   | 1        | Storage de mídia |
| Ingress    | `Ingress` (requer controller, ex.: ingress-nginx, instalado à parte no cluster) | —          | 80/443      | —        | Roteamento externo e TLS |

Nenhum componente acessa o banco ou o storage de outro diretamente — tudo
passa pela API do backend, exceto o worker, que acessa banco e fila
diretamente por necessidade de processamento assíncrono.

## Fluxo do assistente de IA (assíncrono)

1. Editor envia `POST /api/posts/generate-draft` com tópico/instruções.
2. Backend valida o payload, cria um `job` no Redis (fila), retorna `job_id`
   imediatamente (202 Accepted).
3. `worker` consome o job, chama a API da LLM, salva o resultado no MySQL
   (tabela `assistant_drafts`) e atualiza o status do job no Redis.
4. Frontend faz polling em `GET /api/posts/generate-draft/{job_id}` (ou
   consome via SSE, a definir na spec da feature) até status `done`.
5. Editor revisa o conteúdo gerado e decide salvar como Draft.

Motivo de ser assíncrono: geração de texto por LLM pode levar vários segundos;
não deve travar a requisição HTTP nem o event loop do FastAPI.

## Configuração (variáveis de ambiente)

Entregues aos pods via `ConfigMap` (valores não sensíveis) + `Secret`
(credenciais) — nunca hardcoded no manifest do `Deployment`. Ver
`k8s/01-configmap.yaml` e `k8s/02-secret.example.yaml` (template; o
`k8s/secret.yaml` real, preenchido, nunca é commitado — listado no
`.gitignore` da raiz do repo).

```
# ConfigMap `backend-config` (não sensível)
ENVIRONMENT=production
JWT_ALGORITHM=HS256
JWT_EXPIRES_MIN=60
REDIS_URL=redis://redis:6379/0   # DNS interno do cluster, sem autenticação configurada
CORS_ALLOWED_ORIGINS=["http://blog.local"]   # origem do frontend (SPEC-001) — cookies httpOnly cross-origin exigem lista explícita, nunca "*"
LLM_MODEL=claude-sonnet-4-6

# Secret `backend-secrets` (sensível)
DATABASE_URL=mysql+asyncmy://blog:<senha>@mysql:3306/blog
JWT_SECRET=<gerado com openssl rand -hex 32>
LLM_API_KEY=<chave da API da LLM>

# frontend (build-time — embutido no bundle cliente, ver docker/frontend.Dockerfile)
NEXT_PUBLIC_API_URL=http://backend:8000
```

## Rede

Cada componente tem um `Service` `ClusterIP` próprio, resolvido por DNS
interno do cluster dentro do namespace `sdd-blog-cms` (`mysql`, `redis`,
`minio`, `backend`, `frontend`). `mysql` usa `Service` headless
(`clusterIP: None`), convenção padrão para `StatefulSet` de réplica única.
Apenas o `Ingress` expõe tráfego para fora do cluster — `frontend` e
`backend` não têm IP externo, tudo passa pelo Ingress controller.

## Decisões e trade-offs

- **MySQL em vez de PostgreSQL**: a feature de IA da v1 (redação de rascunhos)
  não depende de busca vetorial/embeddings. Se no futuro entrar RAG (ex:
  "manter o estilo dos posts anteriores"), reavaliar migração para Postgres +
  pgvector — a camada de acesso a dados deve ficar isolada em `services/` para
  facilitar essa troca.
- **FastAPI em vez de ASP.NET**: melhor integração com SDKs de IA (Python é o
  ecossistema dominante) e tipagem forte via Pydantic, que serve como contrato
  vivo entre front e back (compatível com o espírito de SDD).
- **Worker separado**: evita bloquear requisições HTTP com chamadas de LLM
  potencialmente lentas.
- **Kubernetes em vez de Docker Compose**: orquestração alvo de produção
  (self-healing de pods, `Deployment` com múltiplas réplicas para
  frontend/backend, `PersistentVolumeClaim` para os componentes com estado).
  Custo: mais peças móveis que Compose para rodar localmente — requer um
  cluster local (kind/minikube/Docker Desktop Kubernetes) em vez de um único
  `docker compose up`. Os `Dockerfile`s em `docker/` continuam sendo a forma
  de construir as imagens; só a orquestração muda.
