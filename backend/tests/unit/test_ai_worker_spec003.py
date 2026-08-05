"""Testes unitários — `app.workers.ai_worker` (SPEC-003 / achado R7 do ai-safety-reviewer).

`ai-safety-reviewer` apontou que nenhum worker de verdade consumia a fila de
jobs (`JobQueue`) enfileirada por `POST /api/posts/generate-draft` — a
arquitetura descrita em `specs/ARCHITECTURE.md` ("worker consome o job,
chama a API da LLM...") não tinha nenhuma peça de código correspondente
entre "enfileirar" e `process_job`.

`app.workers.ai_worker.process_one` é essa peça: consome (`dequeue`) um
único `job_id` da fila e chama `process_job`. É só essa lógica que é testada
aqui, com fakes 100% em memória (`FakeJobQueue`/`FakeAiClient`, reaproveitados
de `test_ai_assistant_service_spec003.py`, sem modificá-los) e um
`db_session` SQLite in-memory — o loop infinito de produção (`run_worker`)
não é exercitado (infraestrutura, não lógica de negócio, ver
`specs/TESTING.md`).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.assistant_draft import AssistantDraft, JobStatus
from app.workers.ai_worker import process_one
from tests.unit.test_ai_assistant_service_spec003 import (
    VALID_LLM_RESULT,
    FakeAiClient,
    FakeJobQueue,
)


async def _seed_pending_job(db_session, *, editor_id: str) -> str:
    job = AssistantDraft(
        id=str(uuid.uuid4()),
        editor_id=editor_id,
        status=JobStatus.PENDING,
        topic="Tópico de teste do worker",
        tone="tecnico",
        keywords=["a"],
        length="medium",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job.id


async def test_process_one_dequeues_and_processes_a_pending_job_spec003(
    db_session, seed_editor_user
) -> None:
    user, _raw_password = seed_editor_user
    job_id = await _seed_pending_job(db_session, editor_id=user.id)
    job_queue = FakeJobQueue()
    job_queue.enqueued_job_ids.append(job_id)
    ai_client = FakeAiClient(response=VALID_LLM_RESULT)

    processed = await process_one(db_session, ai_client, job_queue)

    assert processed is True
    assert len(ai_client.calls) == 1
    result = await db_session.execute(select(AssistantDraft).where(AssistantDraft.id == job_id))
    job = result.scalar_one()
    assert job.status == JobStatus.DONE
    assert job.result_title == VALID_LLM_RESULT["title"]


async def test_process_one_returns_false_when_queue_is_empty_spec003(db_session) -> None:
    job_queue = FakeJobQueue()
    ai_client = FakeAiClient()

    processed = await process_one(db_session, ai_client, job_queue)

    assert processed is False
    # A LLM nunca é chamada quando não há job a processar.
    assert ai_client.calls == []


async def test_process_one_consumes_jobs_in_fifo_order_spec003(
    db_session, seed_editor_user
) -> None:
    user, _raw_password = seed_editor_user
    first_job_id = await _seed_pending_job(db_session, editor_id=user.id)
    second_job_id = await _seed_pending_job(db_session, editor_id=user.id)
    job_queue = FakeJobQueue()
    job_queue.enqueued_job_ids.extend([first_job_id, second_job_id])
    ai_client = FakeAiClient(response=VALID_LLM_RESULT)

    await process_one(db_session, ai_client, job_queue)

    # Só o primeiro job da fila foi processado nesta chamada; o segundo
    # continua enfileirado, aguardando a próxima iteração do worker.
    result = await db_session.execute(
        select(AssistantDraft).where(AssistantDraft.id == first_job_id)
    )
    assert result.scalar_one().status == JobStatus.DONE
    result = await db_session.execute(
        select(AssistantDraft).where(AssistantDraft.id == second_job_id)
    )
    assert result.scalar_one().status == JobStatus.PENDING
    assert job_queue.enqueued_job_ids == [second_job_id]
