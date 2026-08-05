"""Blacklist de refresh tokens (RF06 — logout invalida sessão).

Em produção, a blacklist vive no Redis (chave = `jti` do refresh token, TTL =
tempo restante até a expiração do token). Em testes unitários, `get_token_blacklist`
é substituída via `app.dependency_overrides` por um fake 100% em memória
(`InMemoryTokenBlacklist`, em `backend/tests/conftest.py`) — por isso esta
dependency é implementada como uma função (não uma instância global fixa),
para ser "override-ável".
"""

from __future__ import annotations

from typing import Protocol

import redis.asyncio as aioredis

from app.core.config import get_settings


class TokenBlacklist(Protocol):
    """Interface que qualquer implementação de blacklist deve satisfazer."""

    async def add(self, jti: str, ttl_seconds: int) -> None:
        """Adiciona `jti` à blacklist, expirando automaticamente em `ttl_seconds`."""
        ...

    async def is_blacklisted(self, jti: str) -> bool:
        """Retorna `True` se `jti` estiver na blacklist (token invalidado)."""
        ...


class RedisTokenBlacklist:
    """Implementação de `TokenBlacklist` usando Redis (produção)."""

    _KEY_PREFIX = "auth:refresh-blacklist:"

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def add(self, jti: str, ttl_seconds: int) -> None:
        client = self._get_client()
        await client.set(f"{self._KEY_PREFIX}{jti}", "1", ex=max(ttl_seconds, 1))

    async def is_blacklisted(self, jti: str) -> bool:
        client = self._get_client()
        exists = await client.exists(f"{self._KEY_PREFIX}{jti}")
        return bool(exists)


_redis_blacklist: RedisTokenBlacklist | None = None


def get_token_blacklist() -> TokenBlacklist:
    """Dependency FastAPI: fornece a blacklist de refresh tokens.

    Override-ável em testes via
    `app.dependency_overrides[get_token_blacklist] = lambda: fake_instance`.
    """

    global _redis_blacklist
    if _redis_blacklist is None:
        settings = get_settings()
        _redis_blacklist = RedisTokenBlacklist(settings.redis_url)
    return _redis_blacklist
