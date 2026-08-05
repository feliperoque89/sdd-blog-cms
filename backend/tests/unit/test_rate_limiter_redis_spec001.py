"""Testes unitários de `app.services.rate_limiter` (SPEC-001, RNF02).

`RedisLoginRateLimiter` é a implementação usada em produção (Redis). Estes
testes mockam completamente o client Redis (`redis.asyncio.Redis`) — nenhuma
chamada de rede real acontece, conforme `specs/TESTING.md`.

O comportamento de "5 tentativas/min por IP" observável via API já é
coberto (com o fake em memória) por `test_auth_service_spec001.py`; aqui o
foco é a implementação Redis em si, que não é exercitada por nenhum outro
teste (a app FastAPI de teste sempre faz override de `get_login_rate_limiter`).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import rate_limiter as rl_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Garante isolamento entre testes do singleton módulo de `get_login_rate_limiter`."""

    rl_module._redis_rate_limiter = None
    yield
    rl_module._redis_rate_limiter = None


async def test_redis_rate_limiter_allows_and_sets_expiry_on_first_attempt_spec001() -> None:
    limiter = rl_module.RedisLoginRateLimiter(
        "redis://fake:6379/0", max_attempts=5, window_seconds=60
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 1
    limiter._client = mock_client

    allowed = await limiter.is_allowed("127.0.0.1")

    assert allowed is True
    mock_client.incr.assert_awaited_once_with("auth:login-attempts:127.0.0.1")
    mock_client.expire.assert_awaited_once_with("auth:login-attempts:127.0.0.1", 60)


async def test_redis_rate_limiter_allows_without_resetting_expiry_after_first_attempt_spec001() -> (
    None
):
    limiter = rl_module.RedisLoginRateLimiter(
        "redis://fake:6379/0", max_attempts=5, window_seconds=60
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 3
    limiter._client = mock_client

    allowed = await limiter.is_allowed("127.0.0.1")

    assert allowed is True
    mock_client.expire.assert_not_awaited()


async def test_redis_rate_limiter_blocks_after_max_attempts_spec001() -> None:
    limiter = rl_module.RedisLoginRateLimiter(
        "redis://fake:6379/0", max_attempts=5, window_seconds=60
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 6
    limiter._client = mock_client

    allowed = await limiter.is_allowed("127.0.0.1")

    assert allowed is False


def test_redis_rate_limiter_lazily_creates_and_caches_client_spec001(monkeypatch) -> None:
    fake_client = MagicMock()
    from_url_mock = MagicMock(return_value=fake_client)
    monkeypatch.setattr(rl_module.aioredis, "from_url", from_url_mock)

    limiter = rl_module.RedisLoginRateLimiter(
        "redis://fake:6379/0", max_attempts=5, window_seconds=60
    )
    client_first_call = limiter._get_client()
    client_second_call = limiter._get_client()

    from_url_mock.assert_called_once_with("redis://fake:6379/0", decode_responses=True)
    assert client_first_call is client_second_call is fake_client


def test_get_login_rate_limiter_returns_cached_singleton_instance_spec001() -> None:
    first = rl_module.get_login_rate_limiter()
    second = rl_module.get_login_rate_limiter()

    assert first is second
    assert isinstance(first, rl_module.RedisLoginRateLimiter)
