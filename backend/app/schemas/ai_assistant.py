"""Schemas Pydantic do contrato de API do assistente de IA (SPEC-003)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.assistant_draft import JobStatus

Tone = Literal["formal", "casual", "tecnico"]
Length = Literal["short", "medium", "long"]

# RNF03: limites de tamanho em `topic`/`keywords` são a primeira camada de
# defesa contra prompt injection — reduzem a superfície de ataque (payload de
# texto arbitrariamente longo) antes mesmo do dado chegar em
# `app.services.ai_prompts.build_user_message`.
MAX_TOPIC_LENGTH = 500
MAX_KEYWORDS = 10
MAX_KEYWORD_LENGTH = 50

# Achado C1 (ai-safety-reviewer, auditoria SPEC-003): sem teto de tamanho, um
# `title`/`content_markdown` da LLM maior do que as colunas do banco
# (`String(255)` / `Text`, ver `app.models.assistant_draft`) faz o `commit()`
# em `app.services.ai_assistant_service.process_job` levantar `DataError` em
# MySQL (SQLite in-memory dos testes não aplica esse limite, por isso o bug
# não aparecia na suíte). Estes limites garantem que a validação Pydantic
# rejeita a resposta ANTES de qualquer tentativa de persistência.
MAX_TITLE_LENGTH = 255
# TEXT do MySQL comporta 65.535 bytes; utf8mb4 usa até 4 bytes/caractere no
# pior caso, então 16.000 caracteres deixa margem segura (64.000 bytes).
MAX_CONTENT_MARKDOWN_LENGTH = 16_000
MAX_TAG_LENGTH = 50


class GenerateDraftRequest(BaseModel):
    """Payload de `POST /api/posts/generate-draft` (RF01)."""

    topic: str = Field(min_length=1, max_length=MAX_TOPIC_LENGTH)
    tone: Tone
    keywords: list[Annotated[str, Field(max_length=MAX_KEYWORD_LENGTH)]] = Field(
        default_factory=list, max_length=MAX_KEYWORDS
    )
    length: Length


class GenerateDraftAccepted(BaseModel):
    """Resposta `202` de `POST /api/posts/generate-draft` (RF02).

    O `job_id` é retornado imediatamente, sem aguardar a LLM (critério de
    aceite 1) — a geração acontece de forma assíncrona, consumida por um
    worker (ver `specs/ARCHITECTURE.md`).
    """

    job_id: str
    status: JobStatus


class GeneratedDraftResult(BaseModel):
    """Resultado gerado pela LLM (RF04) — validado ESTRITAMENTE antes de salvar.

    `extra="forbid"` (+ todos os campos obrigatórios e tipados) é a defesa
    determinística contra prompt injection descrita nas notas de
    implementação da SPEC-003: qualquer campo fora deste contrato (ex.: um
    campo `system_prompt` "vazado" por uma LLM que obedeceu a uma tentativa
    de injection, ou um tipo incorreto, como `tags` sendo uma string livre em
    vez de lista) faz a validação falhar. `app.services.ai_assistant_service.
    process_job` trata essa falha marcando o job como `failed`, sem nunca
    persistir nem expor o conteúdo rejeitado em nenhuma resposta de API.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    content_markdown: str = Field(min_length=1, max_length=MAX_CONTENT_MARKDOWN_LENGTH)
    meta_description: str = Field(min_length=1, max_length=160)
    tags: list[Annotated[str, Field(max_length=MAX_TAG_LENGTH)]] = Field(max_length=5)


class JobStatusResponse(BaseModel):
    """Resposta de `GET /api/posts/generate-draft/{job_id}` (RF05).

    `result` só é preenchido quando `status == "done"`; `error` (mensagem
    genérica — RNF02) só é preenchido quando `status == "failed"`.
    """

    job_id: str
    status: JobStatus
    result: GeneratedDraftResult | None = None
    error: str | None = None
