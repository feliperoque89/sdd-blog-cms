"""Testes unitários de `app.services.token_blacklist` (SPEC-001, RF06).

`RedisTokenBlacklist` é a implementação usada em produção (Redis). Estes
testes mockam completamente o client Redis (`redis.asyncio.Redis`) — nenhuma
chamada de rede real acontece, conforme `specs/TESTING.md` ("chamadas a
serviços externos... nunca são feitas de verdade em testes unitários").

O caminho "fake em memória" (`InMemoryTokenBlacklist`) usado pelos testes de
integração da API já é coberto por `test_auth_service_spec001.py`; aqui o
foco é a implementação Redis em si, que não é exercitada por nenhum outro
teste (a app FastAPI de teste sempre faz override de `get_token_blacklist`).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import token_blacklist as tb_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Garante isolamento entre testes do singleton módulo de `get_token_blacklist`."""

    tb_module._redis_blacklist = None
    yield
    tb_module._redis_blacklist = None


async def test_redis_token_blacklist_add_stores_jti_with_ttl_spec001() -> None:
    blacklist = tb_module.RedisTokenBlacklist("redis://fake:6379/0")
    mock_client = AsyncMock()
    blacklist._client = mock_client  # já "conectado": evita tocar Redis real

    await blacklist.add("some-jti", ttl_seconds=120)

    mock_client.set.assert_awaited_once_with("auth:refresh-blacklist:some-jti", "1", ex=120)


async def test_redis_token_blacklist_add_enforces_minimum_ttl_of_one_second_spec001() -> None:
    blacklist = tb_module.RedisTokenBlacklist("redis://fake:6379/0")
    mock_client = AsyncMock()
    blacklist._client = mock_client

    await blacklist.add("some-jti", ttl_seconds=0)

    mock_client.set.assert_awaited_once_with("auth:refresh-blacklist:some-jti", "1", ex=1)


async def test_redis_token_blacklist_is_blacklisted_true_when_present_spec001() -> None:
    blacklist = tb_module.RedisTokenBlacklist("redis://fake:6379/0")
    mock_client = AsyncMock()
    mock_client.exists.return_value = 1
    blacklist._client = mock_client

    result = await blacklist.is_blacklisted("some-jti")

    assert result is True
    mock_client.exists.assert_awaited_once_with("auth:refresh-blacklist:some-jti")


async def test_redis_token_blacklist_is_blacklisted_false_when_absent_spec001() -> None:
    blacklist = tb_module.RedisTokenBlacklist("redis://fake:6379/0")
    mock_client = AsyncMock()
    mock_client.exists.return_value = 0
    blacklist._client = mock_client

    assert await blacklist.is_blacklisted("missing-jti") is False


def test_redis_token_blacklist_lazily_creates_and_caches_client_spec001(monkeypatch) -> None:
    fake_client = MagicMock()
    from_url_mock = MagicMock(return_value=fake_client)
    monkeypatch.setattr(tb_module.aioredis, "from_url", from_url_mock)

    blacklist = tb_module.RedisTokenBlacklist("redis://fake:6379/0")
    client_first_call = blacklist._get_client()
    client_second_call = blacklist._get_client()

    from_url_mock.assert_called_once_with("redis://fake:6379/0", decode_responses=True)
    assert client_first_call is client_second_call is fake_client


def test_get_token_blacklist_returns_cached_singleton_instance_spec001() -> None:
    first = tb_module.get_token_blacklist()
    second = tb_module.get_token_blacklist()

    assert first is second
    assert isinstance(first, tb_module.RedisTokenBlacklist)
