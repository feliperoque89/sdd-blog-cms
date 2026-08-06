# SPEC-004 — Configuração do Assistente de IA

## Status
Implementado

## Objetivo
Permitir que o editor/admin configure, via uma tela na área administrativa,
os parâmetros de conexão com a API da LLM (`model`, `base_url`, `api_key` e
demais parâmetros de chamada) usados pelo assistente de IA (SPEC-003), sem
depender exclusivamente de variáveis de ambiente fixadas no deploy do
backend/worker.

## Contexto
SPEC-003 já implementa o assistente de IA, mas os parâmetros de chamada à
LLM (`LLM_MODEL`, `LLM_API_KEY`, `LLM_API_BASE_URL`, `LLM_TIMEOUT_SECONDS`,
`LLM_MAX_OUTPUT_TOKENS`) só existiam como variáveis de ambiente
(`app.core.config.Settings`), exigindo reiniciar o backend/worker para
qualquer troca — inviável para o usuário testar/trocar de provedor ou chave
em uso local/interativo. Esta spec nasceu de um pedido direto do usuário
durante uma sessão de ajuste ("adiciona uma tela de configuração da IA"),
não de um ciclo `/new-spec` → `/implement-spec` completo — registrada aqui
retroativamente para manter a rastreabilidade exigida por `CLAUDE.md`.

## Requisitos funcionais

- RF01: Tela administrativa (`/admin/ai-settings`) com formulário para
  `provider`, `model`, `base_url`, `api_key`, `max_output_tokens` e
  `timeout_seconds`.
- RF02: `GET /api/admin/ai-settings` retorna a configuração atual; se nada
  foi salvo ainda, retorna os valores de fallback (`Settings`/env).
- RF03: `PUT /api/admin/ai-settings` cria ou atualiza a configuração
  (singleton, uma única linha). Nunca é obrigatório reenviar `api_key` — se
  omitida/vazia, a chave já salva é preservada.
- RF04: A resposta de `GET`/`PUT` nunca inclui `api_key` em texto puro —
  apenas `api_key_set` (bool) e `api_key_last4` (últimos 4 caracteres, para
  o usuário confirmar qual chave está ativa).
- RF05: O worker (`app.workers.ai_worker.run_worker`) usa a configuração
  efetiva (banco, com fallback para env) a cada ciclo de processamento —
  uma mudança salva na tela vale na próxima geração, sem reiniciar o
  worker.
- RF06: `provider` seleciona qual API de LLM é chamada: `"anthropic"`
  (Anthropic Messages API, `HttpAiClient`) ou `"gemini"` (Google Gemini
  API, `GeminiAiClient`). `app.services.ai_client.build_ai_client` decide a
  implementação a partir de `LlmConfig.provider`; o worker chama sempre
  `build_ai_client`, nunca instancia `HttpAiClient`/`GeminiAiClient`
  diretamente. Default (quando não configurado nem no banco nem no env):
  `"anthropic"`.
- RF07: `base_url` só é aceito se for um endpoint `https` no host oficial
  do `provider` selecionado (`api.anthropic.com` para `"anthropic"`,
  `generativelanguage.googleapis.com` para `"gemini"`) — validado em
  `AiSettingsInput` antes de persistir. Achado C3/C4 do `ai-safety-reviewer`
  (auditoria desta spec): sem essa checagem, `provider`/`base_url`/`api_key`
  eram aceitos sem nenhuma relação entre si, permitindo que um `editor`
  configurasse a chave de um provider para ser enviada a um host arbitrário
  (exfiltração de segredo/SSRF a partir do worker) ou ao host do outro
  provider. Fora de escopo: apontar para proxy/gateway self-hosted — só os
  hosts oficiais das APIs são aceitos. Essa validação cobre o `PUT`; como
  ressalva residual do mesmo achado, `LLM_PROVIDER`/`LLM_API_BASE_URL`
  (env) são configurados de forma independente e não passam por ela — por
  isso `get_effective_llm_config`/`to_public`
  (`app.services.ai_settings_service`) recompõem silenciosamente o
  `base_url` para o default oficial do provider sempre que a combinação
  efetiva (banco ou env) não bater, em vez de repassar um par incoerente
  para o worker.

## Requisitos não funcionais

- RNF01: Rotas exigem autenticação `editor`|`admin` (mesmo padrão de
  `posts_admin.py`).
- RNF02: `api_key` nunca é logada nem devolvida em texto puro em nenhuma
  resposta de API (mesmo espírito de RNF02 da SPEC-003).

## Contrato de API

### `GET /api/admin/ai-settings` (auth: editor|admin)
Response `200`:
```json
{
  "provider": "anthropic" | "gemini",
  "model": "string",
  "base_url": "string",
  "api_key_last4": "string | null",
  "api_key_set": true,
  "max_output_tokens": 4096,
  "timeout_seconds": 30
}
```

### `PUT /api/admin/ai-settings` (auth: editor|admin)
Request:
```json
{
  "provider": "anthropic" | "gemini (opcional — default \"anthropic\")",
  "model": "string",
  "base_url": "string",
  "api_key": "string | null (opcional — omitido/vazio preserva a chave já salva)",
  "max_output_tokens": 4096,
  "timeout_seconds": 30
}
```
Response `200`: mesmo formato de `GET`. `provider` fora de
`{"anthropic", "gemini"}` retorna `422`.

## Critérios de aceite

1. **Dado** nenhuma configuração salva, **quando** `GET /api/admin/ai-settings`
   é chamado, **então** retorna os valores de fallback do ambiente, com
   `api_key_set: false`.
2. **Dado** um `PUT` com `api_key` preenchida, **quando** consultado depois,
   **então** `api_key_set` é `true` e `api_key_last4` mostra os últimos 4
   caracteres — nunca a chave completa.
3. **Dado** uma configuração já salva, **quando** um novo `PUT` é enviado
   sem `api_key`, **então** a chave anteriormente salva é preservada.
4. **Dado** um usuário sem autenticação, **quando** acessa `GET`/`PUT`,
   **então** recebe `401`.
5. **Dado** uma configuração salva com `model`/`api_key` customizados,
   **quando** o worker processa o próximo job de geração, **então** usa
   esses valores (via `get_effective_llm_config`), não os fixos de
   `Settings`/env.
6. **Dado** um `PUT` com `provider: "gemini"`, **quando** o worker monta o
   client de LLM do próximo job (`build_ai_client`), **então** usa
   `GeminiAiClient` (API da Google), não `HttpAiClient` (Anthropic).
7. **Dado** um `PUT` com `provider` fora de `{"anthropic", "gemini"}`,
   **então** a API retorna `422`.
8. **Dado** um `PUT` com `provider: "gemini"` e `base_url` do host da
   Anthropic (ou qualquer host fora da allowlist do provider escolhido, ou
   não-`https`), **então** a API retorna `422`, sem persistir a configuração.

## Casos de teste obrigatórios

- `GET` sem configuração cai no fallback de `Settings` (env).
- `PUT` cria e mascara a chave corretamente.
- `PUT` subsequente sem `api_key` preserva a chave.
- 401 sem autenticação em `GET`/`PUT`.
- Validação: `model`/`base_url` obrigatórios (422 se ausentes); `provider`
  fora de `{"anthropic", "gemini"}` retorna 422; `base_url` cujo host não
  bate com o `provider` (ou não-`https`) retorna 422.
- `GET` sem configuração salva retorna `provider` do fallback de env
  (default `"anthropic"`).
- `get_effective_llm_config` mescla banco + fallback de env corretamente,
  incluindo `provider`.
- `build_ai_client` retorna `GeminiAiClient` quando `provider == "gemini"`
  e `HttpAiClient` para qualquer outro valor (`"anthropic"`/default).
- `GeminiAiClient.generate`: monta a URL/headers/body no formato da Gemini
  API e extrai `data`/`usage` da resposta (`candidates[...]`/
  `usageMetadata`), incluindo os casos de erro (timeout, HTTP de erro,
  JSON malformado) — mesma cobertura de `HttpAiClient`
  (`test_ai_client_spec003.py`).

## Fora de escopo
- Múltiplas configurações (por usuário/workspace) — singleton único, como o
  restante do backend (single-tenant).
- Validação ativa da chave (ex.: chamar a API da LLM para confirmar que a
  chave é válida antes de salvar) — a chave só é exercitada de fato na
  próxima geração de rascunho.
- Histórico/auditoria de mudanças de configuração.
- Proteção contra SSRF por DNS rebinding/DNS interno resolvendo os hosts
  oficiais (`api.anthropic.com`/`generativelanguage.googleapis.com`) para
  um IP interno — a allowlist de RF07 valida hostname, não IP resolvido.
  Risco aceito neste escopo (avaliação do `ai-safety-reviewer`, auditoria
  desta spec): `editor`/`admin` são papéis de confiança em um CMS
  single-tenant, e um atacante nessa posição já precisaria controlar a
  resolução DNS do cluster — nesse ponto o comprometimento vai muito além
  desta tela.
