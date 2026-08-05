"""Testes unitários — R3 (SPEC-003 / achado do ai-safety-reviewer).

`ai-safety-reviewer` apontou que `process_job` só tratava explicitamente
`AiClientError`/`ValidationError`/`TimeoutError`, deixando qualquer outra
exceção inesperada (ex.: um bug no client de IA, um erro genérico de
infraestrutura) escapar — o que derrubaria o worker/processo em produção em
vez de marcar o job como `failed`.

`process_job` agora tem um `except Exception` final que também marca o job
como `failed` (mesma mensagem genérica — RNF02), loga apenas o TIPO da
exceção (nunca a mensagem interna completa, que poderia conter dados
sensíveis) e nunca deixa a exceção propagar.

Reaproveita `FakeAiClient`/fixtures de `test_ai_assistant_service_spec003.py`
sem modificá-los.
"""

from __future__ import annotations

import logging

from httpx import AsyncClient

from app.services.ai_assistant_service import process_job
from tests.unit.test_ai_assistant_service_spec003 import (  # noqa: F401 - fixture overrides
    FakeAiClient,
    _create_job,
    app,
    fake_ai_client,
    fake_ai_rate_limiter,
    fake_job_queue,
)

GENERATE_DRAFT_URL = "/api/posts/generate-draft"


async def test_process_job_unexpected_exception_marks_job_as_failed_spec003(
    editor_client: AsyncClient, db_session
) -> None:
    """Uma exceção genérica e inesperada (não `AiClientError`/`ValidationError`
    /`TimeoutError`) levantada pelo client de IA não pode derrubar o
    processamento: o job deve virar `failed`, com a mesma mensagem genérica
    de qualquer outra falha."""

    job_id = await _create_job(editor_client)
    internal_detail = "bug interno inesperado (nao deveria vazar: token=sk-shouldnotleak)"
    ai_client = FakeAiClient(error=RuntimeError(internal_detail))

    await process_job(db_session, ai_client, job_id)  # não deve levantar exceção

    response = await editor_client.get(f"{GENERATE_DRAFT_URL}/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body.get("result") is None
    assert body.get("error")
    assert "sk-shouldnotleak" not in body["error"]
    assert internal_detail not in body["error"]


async def test_process_job_unexpected_exception_is_logged_without_full_detail_spec003(
    editor_client: AsyncClient, db_session, caplog
) -> None:
    job_id = await _create_job(editor_client)
    internal_detail = "detalhe interno sensível que não deve ir para o log completo"
    ai_client = FakeAiClient(error=RuntimeError(internal_detail))

    with caplog.at_level(logging.ERROR, logger="app.services.ai_assistant_service"):
        await process_job(db_session, ai_client, job_id)

    full_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "RuntimeError" in full_log_text
    assert internal_detail not in full_log_text


async def test_process_job_with_nonexistent_job_id_is_a_noop_spec003(db_session) -> None:
    """Defesa extra: `process_job` chamado com um `job_id` que não existe no
    banco (ex.: corrida entre `enqueue` e uma remoção manual) não levanta
    exceção nem tenta chamar a LLM — apenas retorna sem fazer nada."""

    ai_client = FakeAiClient(response={})

    await process_job(db_session, ai_client, "does-not-exist")

    assert ai_client.calls == []


async def test_process_job_unexpected_exception_from_a_second_kind_of_error_spec003(
    editor_client: AsyncClient, db_session
) -> None:
    """Confirma que a proteção não é específica a `RuntimeError`: qualquer
    exceção não prevista é tratada da mesma forma."""

    job_id = await _create_job(editor_client)
    ai_client = FakeAiClient(error=KeyError("chave-inesperada"))

    await process_job(db_session, ai_client, job_id)

    response = await editor_client.get(f"{GENERATE_DRAFT_URL}/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
