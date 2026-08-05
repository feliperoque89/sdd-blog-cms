"""Modelo `AssistantDraft` (SPEC-003 — Assistente de IA para Redação de Posts).

Representa um job de geração de rascunho via LLM (RF02/RF06): criado com
`status=pending` ao ser enfileirado, atualizado para `done` (com os campos
`result_*` preenchidos) ou `failed` (com `error` preenchido, mensagem
genérica — RNF02) quando o worker (`app.services.ai_assistant_service.
process_job`) o processa. Nunca vira um `Post` automaticamente (RF06) — isso
é uma ação explícita e separada do editor, fora do escopo desta spec.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobStatus(str, enum.Enum):
    """Status de um job de geração (contrato de API: `"pending" | "done" | "failed"`)."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class AssistantDraft(Base):
    """Job de geração de rascunho de post via IA, vinculado ao editor solicitante."""

    __tablename__ = "assistant_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    editor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(
            JobStatus,
            name="assistant_draft_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=JobStatus.PENDING,
    )

    # Parâmetros solicitados pelo editor (RF01).
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(20), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    length: Mapped[str] = mapped_column(String(20), nullable=False)

    # Resultado gerado pela LLM (RF04), preenchido apenas quando `status=done`.
    result_title: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    result_content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    result_meta_description: Mapped[str | None] = mapped_column(
        String(160), nullable=True, default=None
    )
    result_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None)

    # Mensagem de erro genérica (RNF02 — nunca a exceção interna), preenchida
    # apenas quando `status=failed`.
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"AssistantDraft(id={self.id!r}, status={self.status!r})"
