"""Testes unitários — SPEC-001 (Autenticação Admin/Editor).

Fonte: specs/features/SPEC-001-auth.md

Cobre os 5 critérios de aceite e os 8 casos de teste obrigatórios listados na
spec. Nenhum teste aqui depende de infraestrutura real: banco é SQLite
in-memory (fixture `db_session`/`client` em `conftest.py`) e a blacklist de
refresh token / rate limiter (Redis em produção) são fakes 100% em memória
(`InMemoryTokenBlacklist`, `InMemoryLoginRateLimiter`).

Mapeamento critério de aceite -> teste:
1. Login OK -> cookie httpOnly + 200 com dados do usuário
   -> test_login_success_sets_httponly_cookies_and_returns_user_data_spec001
2. Credenciais inválidas -> 401, nenhuma sessão criada
   -> test_login_wrong_password_returns_401_and_creates_no_session_spec001
3. Token expirado em rota protegida -> 401
   -> test_access_protected_route_with_expired_token_returns_401_spec001
4. Papel `editor` em rota admin-only -> 403
   -> test_editor_role_accessing_admin_only_route_returns_403_spec001
5. Logout invalida refresh token -> requisições seguintes retornam 401
   -> test_logout_invalidates_refresh_token_and_subsequent_requests_return_401_spec001

Casos de teste obrigatórios adicionais (TESTING.md / seção "Casos de teste
obrigatórios" da spec):
- Login com e-mail inexistente
  -> test_login_nonexistent_email_returns_401_spec001
- Acesso a rota protegida sem cookie
  -> test_access_protected_route_without_cookie_returns_401_spec001
- Rate limit bloqueia após N tentativas
  -> test_login_rate_limit_blocks_after_max_attempts_spec001
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.core import security
from app.models.user import User, UserRole
from tests.factories import UserFactory


# ---------------------------------------------------------------------------
# Critério de aceite 1 / caso obrigatório "Login com sucesso"
# ---------------------------------------------------------------------------
async def test_login_success_sets_httponly_cookies_and_returns_user_data_spec001(
    client: AsyncClient, seed_editor_user
) -> None:
    user, raw_password = seed_editor_user

    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": raw_password},
    )

    assert response.status_code == 200

    body = response.json()
    # RF02: o token vai no cookie, nunca no corpo da resposta (contrato de API).
    assert set(body.keys()) == {"id", "name", "role"}
    assert body["id"] == user.id
    assert body["name"] == user.name
    assert body["role"] == user.role
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "password" not in body
    assert "hashed_password" not in body

    set_cookie_headers = response.headers.get_list("set-cookie")
    access_cookie_header = next(
        (h for h in set_cookie_headers if h.startswith("access_token=")), None
    )
    refresh_cookie_header = next(
        (h for h in set_cookie_headers if h.startswith("refresh_token=")), None
    )
    assert access_cookie_header is not None, "cookie access_token não foi setado"
    assert refresh_cookie_header is not None, "cookie refresh_token não foi setado"

    # RNF01/RNF03: cookies httpOnly + SameSite=Strict (Secure é coberto à
    # parte, pois em ambiente de teste COOKIE_SECURE=false).
    for header in (access_cookie_header, refresh_cookie_header):
        assert "HttpOnly" in header
        assert "SameSite=Strict" in header

    assert client.cookies.get("access_token") is not None
    assert client.cookies.get("refresh_token") is not None


# ---------------------------------------------------------------------------
# Critério de aceite 2 / caso obrigatório "Login com senha errada"
# ---------------------------------------------------------------------------
async def test_login_wrong_password_returns_401_and_creates_no_session_spec001(
    client: AsyncClient, seed_editor_user
) -> None:
    user, _correct_password = seed_editor_user

    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "senha-completamente-errada"},
    )

    assert response.status_code == 401
    assert response.headers.get_list("set-cookie") == []
    assert client.cookies.get("access_token") is None
    assert client.cookies.get("refresh_token") is None

    # Nenhuma sessão criada -> uma rota protegida continua não autenticada.
    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 401


# ---------------------------------------------------------------------------
# Caso obrigatório "Login com e-mail inexistente"
# ---------------------------------------------------------------------------
async def test_login_nonexistent_email_returns_401_spec001(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": "nao-cadastrado@example.com", "password": "qualquer-coisa"},
    )

    assert response.status_code == 401
    assert response.headers.get_list("set-cookie") == []


# ---------------------------------------------------------------------------
# Critério de aceite 3 / caso obrigatório "Acesso a rota protegida com token
# expirado"
# ---------------------------------------------------------------------------
async def test_access_protected_route_with_expired_token_returns_401_spec001(
    client: AsyncClient, seed_editor_user
) -> None:
    user, _raw_password = seed_editor_user

    expired_access_token = security.create_access_token(
        data={"sub": user.id, "role": user.role, "type": "access"},
        expires_delta=timedelta(minutes=-5),
    )
    client.cookies.set("access_token", expired_access_token)

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Caso obrigatório "Acesso a rota protegida sem cookie"
# ---------------------------------------------------------------------------
async def test_access_protected_route_without_cookie_returns_401_spec001(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Critério de aceite 4 / caso obrigatório "Acesso a rota admin-only com papel
# editor (403)"
#
# SPEC-001 não define, em seu contrato de API, uma rota de negócio
# admin-only concreta (isso pertence a specs futuras, ex.: SPEC-002 de
# posts). Para testar isoladamente o mecanismo de RBAC
# (`app.api.deps.require_role`) que essas specs futuras vão reutilizar,
# montamos aqui uma mini app FastAPI "probe", só para este teste, com uma
# única rota protegida por `require_role("admin")`. Isso não é código de
# produção: é só um fixture de teste local.
# ---------------------------------------------------------------------------
def _build_admin_only_probe_app(current_user: User) -> FastAPI:
    probe_app = FastAPI()

    @probe_app.get("/__probe__/admin-only")
    async def admin_only_route(
        user: User = Depends(deps.require_role("admin")),
    ) -> dict[str, str]:
        return {"ok": "true", "user_id": user.id}

    probe_app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return probe_app


async def test_editor_role_accessing_admin_only_route_returns_403_spec001() -> None:
    editor_user = UserFactory.build(role=UserRole.EDITOR)
    probe_app = _build_admin_only_probe_app(editor_user)

    transport = ASGITransport(app=probe_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as probe_client:
        response = await probe_client.get("/__probe__/admin-only")

    assert response.status_code == 403


async def test_admin_role_accessing_admin_only_route_returns_200_spec001() -> None:
    """Complementa o critério 4: confirma que o guard de RBAC não bloqueia
    indiscriminadamente — só nega o papel sem permissão."""
    admin_user = UserFactory.build(role=UserRole.ADMIN)
    probe_app = _build_admin_only_probe_app(admin_user)

    transport = ASGITransport(app=probe_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as probe_client:
        response = await probe_client.get("/__probe__/admin-only")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Critério de aceite 5 / caso obrigatório "Logout invalida sessão"
# ---------------------------------------------------------------------------
async def test_logout_invalidates_refresh_token_and_subsequent_requests_return_401_spec001(
    client: AsyncClient, seed_editor_user, token_blacklist
) -> None:
    user, raw_password = seed_editor_user

    login_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert login_response.status_code == 200

    refresh_token_value = client.cookies.get("refresh_token")
    assert refresh_token_value is not None
    refresh_payload = security.decode_token(refresh_token_value)
    refresh_jti = refresh_payload["jti"]

    assert await token_blacklist.is_blacklisted(refresh_jti) is False

    logout_response = await client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    # RF06: refresh token entra na blacklist (Redis em produção; fake em teste).
    assert await token_blacklist.is_blacklisted(refresh_jti) is True

    # Cookies limpos pelo backend (Set-Cookie expirando access/refresh).
    assert client.cookies.get("access_token") is None
    assert client.cookies.get("refresh_token") is None

    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 401


# ---------------------------------------------------------------------------
# RNF02 / caso obrigatório "Rate limit bloqueia após N tentativas"
#
# A spec (specs/features/SPEC-001-auth.md, RNF02) não define o status HTTP
# exato retornado quando o rate limit é excedido. Assumimos 429 Too Many
# Requests (padrão HTTP, RFC 6585) — suposição a confirmar com o time ao
# implementar; se divergir, ajustar esta constante e a asserção abaixo.
# ---------------------------------------------------------------------------
RATE_LIMIT_STATUS_CODE = 429


async def test_login_rate_limit_blocks_after_max_attempts_spec001(
    client: AsyncClient, seed_editor_user
) -> None:
    user, raw_password = seed_editor_user
    wrong_payload = {"email": user.email, "password": "senha-errada"}

    # RNF02: 5 tentativas/min por IP. As 5 primeiras (com senha errada)
    # devem ser processadas normalmente (401), só a 6ª deve ser barrada pelo
    # rate limiter.
    responses = [await client.post("/api/auth/login", json=wrong_payload) for _ in range(5)]
    assert all(r.status_code == 401 for r in responses)

    # A 6ª tentativa, mesmo com credenciais CORRETAS, deve ser bloqueada —
    # prova que o limite é por IP/tentativa, não por "senha errada".
    sixth_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert sixth_response.status_code == RATE_LIMIT_STATUS_CODE


# ---------------------------------------------------------------------------
# RNF01 — senha nunca em texto puro (unitário puro, sem precisar de app/DB).
# ---------------------------------------------------------------------------
def test_hash_password_never_stores_plaintext_spec001() -> None:
    plain = "Str0ng!Passw0rd123"

    hashed = security.hash_password(plain)

    assert hashed != plain
    assert len(hashed) > 0


def test_verify_password_accepts_correct_and_rejects_wrong_password_spec001() -> None:
    plain = "Str0ng!Passw0rd123"
    hashed = security.hash_password(plain)

    assert security.verify_password(plain, hashed) is True
    assert security.verify_password("outra-senha-qualquer", hashed) is False


# ---------------------------------------------------------------------------
# Robustez extra do RF05 (rota protegida): token malformado/adulterado
# também deve ser tratado como não autenticado (401), não como erro 500.
# ---------------------------------------------------------------------------
async def test_access_protected_route_with_malformed_token_returns_401_spec001(
    client: AsyncClient,
) -> None:
    client.cookies.set("access_token", "isso-nao-e-um-jwt-valido")

    response = await client.get("/api/auth/me")

    assert response.status_code == 401
