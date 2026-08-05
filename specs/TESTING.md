# TESTING.md — Estratégia de Testes

## Status
Ativo

## Princípios

1. Toda funcionalidade descrita em `specs/features/SPEC-XXX-*.md` deve ter
   testes unitários que cobrem cada critério de aceite listado na spec.
2. Nomes de teste referenciam a spec: `test_<comportamento>_specXXX`.
3. Chamadas a serviços externos (LLM, storage, e-mail) **nunca** são feitas de
   verdade em testes unitários — sempre mockadas.
4. Testes de integração (com banco real) ficam separados dos unitários e
   rodam em job próprio no CI.

## Backend (pytest)

- Runner: `pytest` + `pytest-asyncio` (modo `asyncio_mode = auto`).
- Cliente HTTP de teste: `httpx.AsyncClient` contra a app FastAPI (ASGI
  transport, sem subir servidor real).
- Mock da LLM: substituir o client de IA (`app/services/ai_client.py`) por um
  fake via `pytest-mock`/`unittest.mock`, com fixtures para:
  - resposta de sucesso (JSON válido com título/corpo/meta/tags),
  - erro/timeout da API da LLM,
  - resposta malformada (para testar tratamento de erro do backend).
- Dados de teste: `factory_boy` para gerar posts, usuários, categorias.
- Banco nos testes unitários: SQLite in-memory (rápido) ou repositório
  in-memory por trás da interface de `services/`.
- Banco nos testes de integração: MySQL real via `testcontainers-python`,
  isolado em `tests/integration/`.
- Cobertura: `pytest-cov`, mínimo de 80% em `app/`, falha o CI abaixo disso.

### Estrutura

```
backend/tests/
├── unit/
│   ├── test_auth_service_spec001.py
│   ├── test_posts_service_spec002.py
│   └── test_ai_assistant_service_spec003.py
└── integration/
    ├── test_auth_api_spec001.py
    ├── test_posts_api_spec002.py
    └── test_ai_assistant_api_spec003.py
```

## Frontend (Vitest)

- Runner: Vitest (mais rápido que Jest, integra bem com App Router/ESM).
- Componentes: React Testing Library, focando em comportamento visível ao
  usuário (não detalhes de implementação).
- Chamadas de API mockadas via MSW (Mock Service Worker), incluindo o fluxo
  de polling/streaming do assistente de IA.
- Nomeação: `<Componente>.test.tsx`, com describe blocks referenciando a spec.

### Estrutura

```
frontend/tests/
├── unit/
│   ├── LoginForm.test.tsx          # SPEC-001
│   ├── PostEditor.test.tsx         # SPEC-002
│   └── AiAssistantPanel.test.tsx   # SPEC-003
```

## O que sempre precisa de teste

- Casos de sucesso (happy path) de cada endpoint/componente.
- Casos de erro/validação (payload inválido, campos obrigatórios ausentes).
- Casos de autorização (usuário sem permissão tentando acessar rota admin).
- Casos de falha de dependência externa (LLM fora do ar, timeout).
- Casos de borda mencionados explicitamente na spec da feature.

## CI (GitHub Actions) — pipeline por PR

1. Lint (ruff/black no backend, eslint/prettier no frontend).
2. Type check (mypy no backend, `tsc --noEmit` no frontend).
3. Subir MySQL efêmero via `testcontainers-python` (Docker direto — não
   depende de Docker Compose nem do cluster Kubernetes de `k8s/`).
4. Rodar `pytest --cov` (unit + integration).
5. Rodar `vitest run --coverage`.
6. Bloquear merge se: lint falhar, type check falhar, algum teste falhar, ou
   cobertura cair abaixo do threshold (80%).

## Definição de "pronto" (Definition of Done) por spec

Uma spec só é considerada implementada quando:
- [ ] Todos os critérios de aceite têm teste correspondente.
- [ ] Testes passam localmente e no CI.
- [ ] Cobertura da feature ≥ 80%.
- [ ] Nenhuma chamada real a serviços externos ocorre nos testes unitários.
- [ ] `specs/features/SPEC-XXX-*.md` atualizado com status `Implementado`.
