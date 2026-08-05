"""Testes unitários — RNF04 (SPEC-003 / achado C2 do ai-safety-reviewer).

`ai-safety-reviewer` apontou que o uso/custo de tokens da chamada à LLM
nunca era logado (RNF04: "Custo e uso de tokens da chamada devem ser
logados (sem logar o conteúdo completo do prompt em texto plano em
produção)").

`app.services.ai_client.AiClient.generate` agora retorna `AiGenerationResult`
(`data` + `usage: AiUsage`); `app.services.ai_assistant_service.process_job`
loga (`logging`, nível INFO) `job_id`/`tokens_input`/`tokens_output` de cada
chamada bem-sucedida, sem nunca logar o conteúdo do prompt/resposta.

Reaproveita `FakeAiClient`/fixtures de `test_ai_assistant_service_spec003.py`
sem modificá-los (além da extensão aditiva de `usage`, já feita naquele
arquivo).
"""

from __future__ import annotations

import logging

from app.services.ai_assistant_service import process_job
from app.services.ai_client import AiUsage
from tests.unit.test_ai_assistant_service_spec003 import (  # noqa: F401 - fixture overrides
    VALID_LLM_RESULT,
    FakeAiClient,
    _create_job,
    app,
    fake_ai_client,
    fake_ai_rate_limiter,
    fake_job_queue,
)

SENSITIVE_TOPIC = "Tópico secreto do editor que jamais deveria ir para o log em texto plano"


async def test_process_job_logs_token_usage_for_successful_job_spec003(
    editor_client, db_session, caplog
) -> None:
    job_id = await _create_job(editor_client, topic=SENSITIVE_TOPIC)
    ai_client = FakeAiClient(
        response=VALID_LLM_RESULT, usage=AiUsage(tokens_input=321, tokens_output=654)
    )

    with caplog.at_level(logging.INFO, logger="app.services.ai_assistant_service"):
        await process_job(db_session, ai_client, job_id)

    usage_log_records = [
        record
        for record in caplog.records
        if "Uso de tokens" in record.getMessage() and job_id in record.getMessage()
    ]
    assert usage_log_records, f"nenhum log de uso de tokens encontrado: {caplog.records}"
    log_message = usage_log_records[0].getMessage()
    assert "321" in log_message
    assert "654" in log_message


async def test_process_job_token_usage_log_never_includes_prompt_or_response_content_spec003(
    editor_client, db_session, caplog
) -> None:
    job_id = await _create_job(editor_client, topic=SENSITIVE_TOPIC)
    ai_client = FakeAiClient(response=VALID_LLM_RESULT)

    with caplog.at_level(logging.INFO):
        await process_job(db_session, ai_client, job_id)

    full_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert SENSITIVE_TOPIC not in full_log_text
    assert VALID_LLM_RESULT["content_markdown"] not in full_log_text
    assert VALID_LLM_RESULT["title"] not in full_log_text
