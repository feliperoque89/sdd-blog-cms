"""Regra de negócio do assistente de IA (SPEC-003).

Router (`app.api.ai_assistant`) fica responsável apenas por HTTP (status
codes); toda a lógica de negócio — enfileiramento, rate limit e
processamento do job (o que um worker Celery chamaria ao consumir a fila,
ver `specs/ARCHITECTURE.md`) — vive aqui.

`process_job` nunca deixa uma exceção escapar (nem de `AiClientError`, nem
de validação de schema): sempre marca o job como `done` ou `failed`, com uma
mensagem de erro genérica (RNF02) — o detalhe interno (timeout, resposta
malformada, chave de API etc.) só vai para o log (RNF04), nunca para o
cliente.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Protocol

import redis.asyncio as aioredis
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.assistant_draft import AssistantDraft, JobStatus
from app.models.user import User, UserRole
from app.schemas.ai_assistant import GeneratedDraftResult, GenerateDraftRequest
from app.services.ai_client import AiClient, AiClientError
from app.services.ai_prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_CANARY, build_user_message

logger = logging.getLogger(__name__)

# RNF02: mensagem genérica devolvida ao cliente — nunca o detalhe interno da
# exceção (stack trace, chave de API, corpo malformado da resposta etc.).
_GENERIC_PROCESSING_ERROR = (
    "Não foi possível gerar o rascunho no momento. Tente novamente mais tarde."
)


class AiRateLimitExceededError(Exception):
    """Limite de gerações de IA excedido para o editor (RF07)."""


class JobQueue(Protocol):
    """Interface de enfileiramento de jobs de geração (modela o Redis, produção)."""

    async def enqueue(self, job_id: str) -> None:
        """Enfileira `job_id` para processamento assíncrono por um worker."""
        ...

    async def dequeue(self, timeout_seconds: int = 5) -> str | None:
        """Retira o próximo `job_id` da fila (bloqueante/via polling).

        Retorna `None` se a fila estiver vazia (timeout). Consumida por
        `app.workers.ai_worker` (R7) — a peça que liga "enfileirar" (RF02) a
        "processar" (`process_job`), ver `specs/ARCHITECTURE.md`.
        """
        ...


class AiRateLimiter(Protocol):
    """Interface de rate limit de gerações de IA por editor (RF07)."""

    async def is_allowed(self, key: str) -> bool:
        """Retorna `True` se mais uma geração para `key` (id do editor) for permitida."""
        ...


class RedisJobQueue:
    """Implementação de `JobQueue` usando uma lista Redis (produção).

    Um worker Celery consome esta fila (`BLPOP`/similar) e chama
    `process_job` para cada `job_id` (ver `specs/ARCHITECTURE.md`).
    """

    _QUEUE_KEY = "ai:generate-draft-jobs"

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            # `socket_timeout=None`: `dequeue` faz BLPOP, cujo tempo de
            # espera já é limitado pelo parâmetro `timeout` do próprio
            # comando (bloqueio no SERVIDOR). O socket_timeout padrão do
            # redis-py (`redis._defaults.DEFAULT_SOCKET_TIMEOUT`, 5s) tem o
            # MESMO valor do `timeout_seconds` default de `dequeue` — as
            # duas contagens correm em paralelo e competem, então o cliente
            # pode estourar o timeout de LEITURA do socket bem no instante
            # em que o BLPOP estava prestes a devolver "fila vazia",
            # levantando `redis.exceptions.TimeoutError` em vez de `None`.
            # Isso nunca aparece nos testes unitários (sempre usam
            # `FakeJobQueue`, nunca um Redis real) — só foi reproduzido
            # rodando o worker de verdade num cluster Kubernetes contra um
            # Redis real (ver k8s/07-worker.yaml), onde o worker entrava em
            # `CrashLoopBackOff` a cada ciclo de fila vazia.
            self._client = aioredis.from_url(
                self._redis_url, decode_responses=True, socket_timeout=None
            )
        return self._client

    async def enqueue(self, job_id: str) -> None:
        client = self._get_client()
        await client.rpush(self._QUEUE_KEY, job_id)

    async def dequeue(self, timeout_seconds: int = 5) -> str | None:
        client = self._get_client()
        result = await client.blpop([self._QUEUE_KEY], timeout=timeout_seconds)
        if result is None:
            return None
        _key, job_id = result
        return str(job_id)


class RedisAiRateLimiter:
    """Implementação de `AiRateLimiter` usando Redis (produção), por editor (RF07)."""

    _KEY_PREFIX = "ai:generate-draft-attempts:"

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


_redis_job_queue: RedisJobQueue | None = None
_redis_ai_rate_limiter: RedisAiRateLimiter | None = None


def get_job_queue() -> JobQueue:
    """Dependency FastAPI: fornece a fila de jobs de geração.

    Override-ável em testes via
    `app.dependency_overrides[get_job_queue] = lambda: fake_instance`.
    """

    global _redis_job_queue
    if _redis_job_queue is None:
        settings = get_settings()
        _redis_job_queue = RedisJobQueue(settings.redis_url)
    return _redis_job_queue


def get_ai_rate_limiter() -> AiRateLimiter:
    """Dependency FastAPI: fornece o rate limiter de gerações de IA (RF07).

    Override-ável em testes via
    `app.dependency_overrides[get_ai_rate_limiter] = lambda: fake_instance`.
    """

    global _redis_ai_rate_limiter
    if _redis_ai_rate_limiter is None:
        settings = get_settings()
        _redis_ai_rate_limiter = RedisAiRateLimiter(
            redis_url=settings.redis_url,
            max_attempts=settings.rate_limit_ai_max_attempts,
            window_seconds=settings.rate_limit_ai_window_seconds,
        )
    return _redis_ai_rate_limiter


async def create_generation_job(
    db: AsyncSession,
    *,
    editor_id: str,
    payload: GenerateDraftRequest,
    rate_limiter: AiRateLimiter,
    job_queue: JobQueue,
) -> AssistantDraft:
    """Cria e enfileira um job de geração de rascunho (RF01/RF02/RF06/RF07).

    Levanta `AiRateLimitExceededError` se `editor_id` excedeu o limite de
    gerações por hora (RF07); o router traduz isso em `429`.
    """

    if not await rate_limiter.is_allowed(editor_id):
        raise AiRateLimitExceededError()

    job = AssistantDraft(
        id=str(uuid.uuid4()),
        editor_id=editor_id,
        status=JobStatus.PENDING,
        topic=payload.topic,
        tone=payload.tone,
        keywords=list(payload.keywords),
        length=payload.length,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await job_queue.enqueue(job.id)
    return job


async def get_job_status(db: AsyncSession, job_id: str) -> AssistantDraft | None:
    """Busca um job de geração pelo id (RF05). `None` se não existir.

    Sem checagem de autorização — uso interno (ex.: `process_job`, que
    precisa acessar qualquer job independentemente de quem o solicitou). Uso
    externo/HTTP deve passar por `get_job_status_for_user`.
    """

    result = await db.execute(select(AssistantDraft).where(AssistantDraft.id == job_id))
    return result.scalar_one_or_none()


async def get_job_status_for_user(
    db: AsyncSession, job_id: str, *, user: User
) -> AssistantDraft | None:
    """Busca um job de geração pelo id, autorizado para `user` (R1).

    Editor só enxerga jobs vinculados ao próprio `editor_id`; admin pode ver
    qualquer job. Retorna `None` tanto se o job não existir quanto se
    existir mas pertencer a outro editor — quem chama (o router) sempre
    traduz isso em `404`, nunca `403`, para não confirmar a terceiros a
    existência de um job de outro usuário.
    """

    job = await get_job_status(db, job_id)
    if job is None:
        return None
    if user.role != UserRole.ADMIN and job.editor_id != user.id:
        return None
    return job


def _contains_system_prompt_canary(result: GeneratedDraftResult) -> bool:
    """RNF03 — defesa por CONTEÚDO (além da estrutural) contra vazamento do
    system prompt.

    Verifica se `SYSTEM_PROMPT_CANARY` (ver `app.services.ai_prompts`)
    aparece em qualquer campo de texto do resultado já validado
    estruturalmente contra `GeneratedDraftResult`. Cobre o caso em que a LLM
    "obedece" a uma tentativa de injection mas devolve o vazamento dentro de
    um campo estruturalmente válido (ex.: embutido em `content_markdown`),
    que a validação de schema sozinha (`extra="forbid"`) não detectaria.
    """

    text_fields = [result.title, result.content_markdown, result.meta_description, *result.tags]
    return any(SYSTEM_PROMPT_CANARY in field for field in text_fields)


async def process_job(db: AsyncSession, ai_client: AiClient, job_id: str) -> None:
    """Processa um job de geração de rascunho (o que um worker Celery chamaria).

    Chama a LLM com o system prompt fixo (nunca exposto — RNF02) e a
    instrução do editor isolada em uma mensagem de usuário separada (RNF03),
    respeitando o timeout de 30s (RNF01). Valida a resposta estritamente
    contra `GeneratedDraftResult` (RF04) antes de salvar e, em seguida,
    verifica se o canário do system prompt vazou para dentro de algum campo
    do resultado (RNF03) — qualquer falha (timeout, resposta não-JSON, campo
    fora do schema, vazamento do system prompt, ou qualquer exceção
    inesperada) marca o job como `failed` com uma mensagem genérica, sem
    nunca propagar a exceção interna para quem chamou nem para nenhuma
    resposta de API. O uso de tokens da chamada é sempre logado (RNF04, nível
    INFO), nunca o conteúdo do prompt/resposta em texto plano.
    """

    job = await get_job_status(db, job_id)
    if job is None:
        return

    try:
        user_message = build_user_message(
            topic=job.topic, tone=job.tone, keywords=job.keywords, length=job.length
        )
        settings = get_settings()
        generation_result = await asyncio.wait_for(
            ai_client.generate(SYSTEM_PROMPT, user_message),
            timeout=settings.llm_timeout_seconds,
        )
        # RNF04: uso/custo de tokens sempre logado — o custo já foi incorrido
        # assim que a LLM respondeu, independentemente do resultado passar
        # na validação de schema abaixo. Nunca loga o prompt/resposta em si.
        logger.info(
            "Uso de tokens da chamada à LLM: job_id=%s tokens_input=%s tokens_output=%s",
            job_id,
            generation_result.usage.tokens_input,
            generation_result.usage.tokens_output,
        )
        result = GeneratedDraftResult.model_validate(generation_result.data)
    except (AiClientError, ValidationError, TimeoutError) as exc:
        logger.warning(
            "Falha ao processar job de geração de rascunho %s: %s", job_id, type(exc).__name__
        )
        job.status = JobStatus.FAILED
        job.error = _GENERIC_PROCESSING_ERROR
        await db.commit()
        return
    except Exception as exc:  # noqa: BLE001 - R3: nenhuma exceção inesperada pode escapar
        logger.error(
            "Falha inesperada ao processar job de geração de rascunho %s: %s",
            job_id,
            type(exc).__name__,
        )
        job.status = JobStatus.FAILED
        job.error = _GENERIC_PROCESSING_ERROR
        await db.commit()
        return

    if _contains_system_prompt_canary(result):
        logger.error(
            "Job de geração de rascunho %s rejeitado: possível vazamento do system prompt "
            "detectado no conteúdo gerado pela LLM.",
            job_id,
        )
        job.status = JobStatus.FAILED
        job.error = _GENERIC_PROCESSING_ERROR
    else:
        job.status = JobStatus.DONE
        job.result_title = result.title
        job.result_content_markdown = result.content_markdown
        job.result_meta_description = result.meta_description
        job.result_tags = list(result.tags)

    # Achado C1 (ai-safety-reviewer, auditoria SPEC-003): este commit também
    # pode falhar (ex.: erro de banco transitório) mesmo com o resultado já
    # validado contra o schema — sem este try/except, essa falha escaparia de
    # `process_job` e derrubaria o worker, quebrando a garantia central do
    # módulo (ver docstring de `process_job`).
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - nenhuma exceção pode escapar daqui
        logger.error(
            "Falha ao persistir resultado do job de geração de rascunho %s: %s",
            job_id,
            type(exc).__name__,
        )
        await db.rollback()
        job.status = JobStatus.FAILED
        job.error = _GENERIC_PROCESSING_ERROR
        try:
            await db.commit()
        except Exception:  # noqa: BLE001 - best-effort; job pode ficar `pending`/inconsistente
            logger.error("Falha ao marcar job %s como 'failed' após erro de persistência.", job_id)
            await db.rollback()
