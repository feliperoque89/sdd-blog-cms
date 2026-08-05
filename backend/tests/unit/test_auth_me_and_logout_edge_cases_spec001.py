"""Testes complementares de SPEC-001 (Autenticação Admin/Editor).

`tests/unit/test_auth_service_spec001.py` (escrito pelo test-writer antes da
implementação) cobre os 5 critérios de aceite e os casos de teste
obrigatórios da spec, mas não exercita:

- O caminho de sucesso (200) de `GET /api/auth/me` — só os caminhos de erro
  (401) estavam cobertos. O contrato de API da spec também define
  explicitamente esse caso: "Response 200: dados do usuário autenticado".
- `POST /api/auth/logout` chamado sem `refresh_token` no cookie, ou com um
  `refresh_token` malformado — casos de robustez de RF06 (logout nunca deve
  quebrar com 500, mesmo sem sessão de refresh válida).

Nenhum destes testes altera os testes já existentes; apenas complementa a
cobertura conforme `specs/TESTING.md` (mínimo 80% em `app/`).
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_get_me_with_valid_session_returns_200_and_user_data_spec001(
    client: AsyncClient, seed_editor_user
) -> None:
    user, raw_password = seed_editor_user

    login_response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": raw_password}
    )
    assert login_response.status_code == 200

    me_response = await client.get("/api/auth/me")

    assert me_response.status_code == 200
    body = me_response.json()
    assert body == {"id": user.id, "name": user.name, "role": user.role}


async def test_logout_without_refresh_cookie_returns_204_spec001(client: AsyncClient) -> None:
    response = await client.post("/api/auth/logout")

    assert response.status_code == 204


async def test_logout_with_malformed_refresh_cookie_returns_204_spec001(
    client: AsyncClient,
) -> None:
    client.cookies.set("refresh_token", "isso-nao-e-um-jwt-valido")

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
