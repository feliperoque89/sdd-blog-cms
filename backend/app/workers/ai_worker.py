"""Worker que consome a fila de jobs de geração de rascunho via IA (SPEC-003 / R7).

Peça que fecha o fluxo assíncrono descrito em `specs/ARCHITECTURE.md`
("Fluxo do assistente de IA"): `POST /api/posts/generate-draft` apenas
enfileira (`JobQueue.enqueue`) e retorna `202` imediatamente; é este módulo
que efetivamente consome a fila (`JobQueue.dequeue`) e chama
`app.services.ai_assistant_service.process_job` para cada `job_id`,
processando a chamada à LLM fora do ciclo de requisição HTTP.

Não usa Celery/RQ de verdade (fora de escopo desta spec, ver
`specs/ARCHITECTURE.md` — "Worker separado"): é um loop simples de consumo
bloqueante/via polling (`JobQueue.dequeue`, implementado via `BLPOP` em
`RedisJobQueue`) — só a peça de infraestrutura que faltava entre "enfileirar"
e "processar". Em produção, roda como o processo do container `worker`
(`docker/`), ver `specs/ARCHITECTURE.md`.

Nunca chamado nos testes unitários com Redis/LLM de verdade: a lógica de
"consumir um item e chamar `process_job`" (`process_one`) é testada
isoladamente com `FakeJobQueue`/`FakeAiClient` e um `db_session` SQLite
in-memory (ver `tests/unit/test_ai_worker_spec003.py`); o loop infinito de
produção (`run_worker`) não é exercitado por nenhum teste (infraestrutura,
não lógica de negócio — `specs/TESTING.md`).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services.ai_assistant_service import JobQueue, get_job_queue, process_job
from app.services.ai_client import AiClient, get_ai_client

logger = logging.getLogger(__name__)


async def process_one(db: AsyncSession, ai_client: AiClient, job_queue: JobQueue) -> bool:
    """Consome um único job da fila e o processa.

    Usada tanto pelo loop de produção (`run_worker`) quanto diretamente pelos
    testes unitários, que dispensam o loop `while True` real.

    Retorna `True` se um job foi encontrado e processado, `False` se a fila
    estava vazia (nada a fazer nesta iteração).
    """

    job_id = await job_queue.dequeue()
    if job_id is None:
        return False

    logger.info("Processando job de geração de rascunho: job_id=%s", job_id)
    await process_job(db, ai_client, job_id)
    return True


async def run_worker() -> None:  # pragma: no cover - loop infinito de produção
    """Loop de produção: consome a fila continuamente.

    Abre uma sessão de banco por iteração processada; se a fila estiver
    vazia, aguarda um curto intervalo antes de tentar novamente (polling).
    Ponto de entrada: `python -m app.workers.ai_worker`, executado como o
    processo do container `worker` (`specs/ARCHITECTURE.md`).
    """

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    job_queue: JobQueue = get_job_queue()
    ai_client: AiClient = get_ai_client()

    logger.info("Worker de geração de rascunhos via IA iniciado.")
    try:
        while True:
            async with session_maker() as db:
                processed = await process_one(db, ai_client, job_queue)
            if not processed:
                await asyncio.sleep(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover - ponto de entrada de produção
    asyncio.run(run_worker())
