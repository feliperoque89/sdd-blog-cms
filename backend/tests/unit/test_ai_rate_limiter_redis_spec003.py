"""Testes unitários de `RedisAiRateLimiter` (SPEC-003, RF07).

`RedisAiRateLimiter` (em `app.services.ai_assistant_service`) é a
implementação usada em produção (Redis) do rate limit de gerações de IA por
editor. Estes testes mockam completamente o client Redis
(`redis.asyncio.Redis`) — nenhuma chamada de rede real acontece, conforme
`specs/TESTING.md`.

O comportamento de "10 gerações/hora" observável via API já é coberto (com o
fake em memória `InMemoryAiRateLimiter`) por
`test_ai_assistant_service_spec003.py`; aqui o foco é a implementação Redis
em si, que não é exercitada por nenhum outro teste (a app FastAPI de teste
sempre faz override de `get_ai_rate_limiter`). Mesmo padrão de
`test_rate_limiter_redis_spec001.py`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import ai_assistant_service as service_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Garante isolamento entre testes do singleton módulo de `get_ai_rate_limiter`."""

    service_module._redis_ai_rate_limiter = None
    yield
    service_module._redis_ai_rate_limiter = None


async def test_redis_ai_rate_limiter_allows_and_sets_expiry_on_first_attempt_spec003() -> None:
    limiter = service_module.RedisAiRateLimiter(
        "redis://fake:6379/0", max_attempts=10, window_seconds=3600
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 1
    limiter._client = mock_client

    allowed = await limiter.is_allowed("editor-1")

    assert allowed is True
    mock_client.incr.assert_awaited_once_with("ai:generate-draft-attempts:editor-1")
    mock_client.expire.assert_awaited_once_with("ai:generate-draft-attempts:editor-1", 3600)


async def test_redis_ai_rate_limiter_allows_without_resetting_expiry_after_first_attempt_spec003() -> (
    None
):
    limiter = service_module.RedisAiRateLimiter(
        "redis://fake:6379/0", max_attempts=10, window_seconds=3600
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 5
    limiter._client = mock_client

    allowed = await limiter.is_allowed("editor-1")

    assert allowed is True
    mock_client.expire.assert_not_awaited()


async def test_redis_ai_rate_limiter_blocks_after_max_attempts_spec003() -> None:
    limiter = service_module.RedisAiRateLimiter(
        "redis://fake:6379/0", max_attempts=10, window_seconds=3600
    )
    mock_client = AsyncMock()
    mock_client.incr.return_value = 11
    limiter._client = mock_client

    allowed = await limiter.is_allowed("editor-1")

    assert allowed is False


def test_redis_ai_rate_limiter_lazily_creates_and_caches_client_spec003(monkeypatch) -> None:
    fake_client = MagicMock()
    from_url_mock = MagicMock(return_value=fake_client)
    monkeypatch.setattr(service_module.aioredis, "from_url", from_url_mock)

    limiter = service_module.RedisAiRateLimiter(
        "redis://fake:6379/0", max_attempts=10, window_seconds=3600
    )
    client_first_call = limiter._get_client()
    client_second_call = limiter._get_client()

    from_url_mock.assert_called_once_with("redis://fake:6379/0", decode_responses=True)
    assert client_first_call is client_second_call is fake_client


def test_get_ai_rate_limiter_returns_cached_singleton_instance_spec003() -> None:
    first = service_module.get_ai_rate_limiter()
    second = service_module.get_ai_rate_limiter()

    assert first is second
    assert isinstance(first, service_module.RedisAiRateLimiter)
