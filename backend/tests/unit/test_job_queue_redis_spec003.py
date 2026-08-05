"""Testes unitários de `RedisJobQueue` (SPEC-003).

`RedisJobQueue` (em `app.services.ai_assistant_service`) é a implementação
usada em produção (Redis) da fila de jobs de geração de rascunho — um worker
Celery consumiria essa fila e chamaria `process_job` (ver
`specs/ARCHITECTURE.md`). Estes testes mockam completamente o client Redis
(`redis.asyncio.Redis`) — nenhuma chamada de rede real acontece, conforme
`specs/TESTING.md`.

O comportamento observável via API (enfileirar sem esperar a LLM) já é
coberto (com o fake em memória `FakeJobQueue`) por
`test_ai_assistant_service_spec003.py`; aqui o foco é a implementação Redis
em si, que não é exercitada por nenhum outro teste (a app FastAPI de teste
sempre faz override de `get_job_queue`). Mesmo padrão de
`test_rate_limiter_redis_spec001.py`/`test_token_blacklist_redis_spec001.py`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import ai_assistant_service as service_module


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Garante isolamento entre testes do singleton módulo de `get_job_queue`."""

    service_module._redis_job_queue = None
    yield
    service_module._redis_job_queue = None


async def test_redis_job_queue_enqueue_pushes_job_id_spec003() -> None:
    queue = service_module.RedisJobQueue("redis://fake:6379/0")
    mock_client = AsyncMock()
    queue._client = mock_client  # já "conectado": evita tocar Redis real

    await queue.enqueue("some-job-id")

    mock_client.rpush.assert_awaited_once_with("ai:generate-draft-jobs", "some-job-id")


async def test_redis_job_queue_dequeue_returns_job_id_from_blpop_spec003() -> None:
    """R7 — `dequeue` é a peça que um worker usa para consumir a fila (`BLPOP`)."""

    queue = service_module.RedisJobQueue("redis://fake:6379/0")
    mock_client = AsyncMock()
    mock_client.blpop.return_value = ("ai:generate-draft-jobs", "some-job-id")
    queue._client = mock_client

    result = await queue.dequeue(timeout_seconds=5)

    assert result == "some-job-id"
    mock_client.blpop.assert_awaited_once_with(["ai:generate-draft-jobs"], timeout=5)


async def test_redis_job_queue_dequeue_returns_none_when_queue_is_empty_spec003() -> None:
    queue = service_module.RedisJobQueue("redis://fake:6379/0")
    mock_client = AsyncMock()
    mock_client.blpop.return_value = None
    queue._client = mock_client

    result = await queue.dequeue()

    assert result is None


def test_redis_job_queue_lazily_creates_and_caches_client_spec003(monkeypatch) -> None:
    fake_client = MagicMock()
    from_url_mock = MagicMock(return_value=fake_client)
    monkeypatch.setattr(service_module.aioredis, "from_url", from_url_mock)

    queue = service_module.RedisJobQueue("redis://fake:6379/0")
    client_first_call = queue._get_client()
    client_second_call = queue._get_client()

    # `socket_timeout=None`: BLPOP em `dequeue` já é limitado pelo timeout do
    # próprio comando (bloqueio no servidor) — o socket_timeout padrão do
    # redis-py (5s, igual ao `timeout_seconds` default de `dequeue`) faria a
    # leitura do cliente estourar na corrida com o retorno normal de "fila
    # vazia", derrubando o worker (reproduzido rodando contra um Redis real
    # em k8s/07-worker.yaml, nunca detectável com um client mockado).
    from_url_mock.assert_called_once_with(
        "redis://fake:6379/0", decode_responses=True, socket_timeout=None
    )
    assert client_first_call is client_second_call is fake_client


def test_get_job_queue_returns_cached_singleton_instance_spec003() -> None:
    first = service_module.get_job_queue()
    second = service_module.get_job_queue()

    assert first is second
    assert isinstance(first, service_module.RedisJobQueue)
