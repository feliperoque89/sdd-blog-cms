# SPEC-001 — Autenticação (Admin/Editor)

## Status
Implementado

## Objetivo
Permitir que Admin e Editor façam login na área restrita, com sessão segura
via JWT armazenado em cookie httpOnly, protegendo todas as rotas `/admin/*`
no frontend e `/api/*` (exceto públicas) no backend.

## Contexto
O blog público não exige autenticação. Apenas a área administrativa
(gestão de posts, categorias, assistente de IA) é restrita a usuários
cadastrados com papel `admin` ou `editor`.

## Requisitos funcionais

- RF01: Usuário faz login com e-mail + senha.
- RF02: Backend retorna um JWT (access token) via cookie httpOnly + secure.
- RF03: Token expira em 60 minutos; refresh token de 7 dias (cookie separado).
- RF04: Rotas `/admin/*` no frontend redirecionam para `/login` se não houver
  sessão válida (validado via middleware do Next.js).
- RF05: Rotas administrativas da API retornam `401` sem cookie válido e `403`
  se o papel não tiver permissão para a ação.
- RF06: Logout invalida o refresh token no backend (blacklist em Redis).

## Requisitos não funcionais

- RNF01: Senhas armazenadas com hash (`bcrypt` ou `argon2`), nunca em texto puro.
- RNF02: Rate limit no endpoint de login (ex: 5 tentativas/min por IP).
- RNF03: Cookies com `SameSite=Strict` e `Secure` em produção.

## Contrato de API

### `POST /api/auth/login`
Request:
```json
{ "email": "editor@exemplo.com", "password": "string" }
```
Response `200`:
```json
{ "id": "uuid", "name": "string", "role": "admin" | "editor" }
```
(o token vai no cookie, não no corpo da resposta)

Response `401`: credenciais inválidas.

### `POST /api/auth/logout`
Response `204`, invalida cookies e refresh token.

### `GET /api/auth/me`
Response `200`: dados do usuário autenticado, `401` se não autenticado.

## Critérios de aceite

1. **Dado** um e-mail e senha corretos, **quando** o usuário faz login,
   **então** recebe cookie httpOnly válido e status 200 com seus dados.
2. **Dado** credenciais inválidas, **quando** tenta logar, **então** recebe 401
   e nenhuma sessão é criada.
3. **Dado** um token expirado, **quando** acessa uma rota protegida,
   **então** recebe 401.
4. **Dado** um usuário com papel `editor`, **quando** tenta acessar uma rota
   restrita a `admin`, **então** recebe 403.
5. **Dado** um usuário autenticado, **quando** faz logout, **então** o
   refresh token é invalidado e novas requisições retornam 401.

## Casos de teste obrigatórios (ver TESTING.md)

- Login com sucesso (unit + integration).
- Login com senha errada.
- Login com e-mail inexistente.
- Acesso a rota protegida sem cookie.
- Acesso a rota protegida com token expirado.
- Acesso a rota `admin-only` com papel `editor` (403).
- Logout invalida sessão.
- Rate limit bloqueia após N tentativas.

## Fora de escopo
- Login social (Google/GitHub OAuth) — considerar em spec futura.
- Recuperação de senha por e-mail — considerar em spec futura.
