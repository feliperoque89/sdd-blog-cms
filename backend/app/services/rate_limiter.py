"""Rate limiter do endpoint de login (RNF02 — 5 tentativas/min por IP).

Em produção, os contadores vivem no Redis (janela fixa por chave = IP do
cliente). Em testes unitários, `get_login_rate_limiter` é substituída via
`app.dependency_overrides` por um fake em memória (`InMemoryLoginRateLimiter`,
em `backend/tests/conftest.py`) — por isso, assim como a blacklist, esta
dependency é uma função (não uma instância global fixa), para ser
"override-ável".
"""

from __future__ import annotations

from typing import Protocol

import redis.asyncio as aioredis

from app.core.config import get_settings


class LoginRateLimiter(Protocol):
    """Interface que qualquer implementação de rate limiter deve satisfazer."""

    async def is_allowed(self, key: str) -> bool:
        """Retorna `True` se mais uma tentativa para `key` (ex.: IP) for permitida."""
        ...


class RedisLoginRateLimiter:
    """Implementação de `LoginRateLimiter` usando Redis (produção).

    Usa uma janela fixa (`INCR` + `EXPIRE` na primeira tentativa da janela).
    Suficiente para o requisito RNF02; uma janela deslizante mais precisa
    pode ser considerada em uma spec futura, se necessário.
    """

    _KEY_PREFIX = "auth:login-attempts:"

    def __init__(self, redis_url: str, max_attempts: int, window_seconds: int) -> None:
        self._redis_url = redis_url
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def is_allowed(self, key: str) -> bool:
        client = self._get_client()
        redis_key = f"{self._KEY_PREFIX}{key}"
        current = await client.incr(redis_key)
        if current == 1:
            await client.expire(redis_key, self.window_seconds)
        return bool(current <= self.max_attempts)


_redis_rate_limiter: RedisLoginRateLimiter | None = None


def get_login_rate_limiter() -> LoginRateLimiter:
    """Dependency FastAPI: fornece o rate limiter de login.

    Override-ável em testes via
    `app.dependency_overrides[get_login_rate_limiter] = lambda: fake_instance`.
    """

    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        settings = get_settings()
        _redis_rate_limiter = RedisLoginRateLimiter(
            redis_url=settings.redis_url,
            max_attempts=settings.rate_limit_login_max_attempts,
            window_seconds=settings.rate_limit_login_window_seconds,
        )
    return _redis_rate_limiter
