"""Modelo `AiSettings` (SPEC-004 — Configuração do Assistente de IA).

Linha única (singleton, id fixo `SINGLETON_ID`) com a configuração de LLM
usada pelo worker (`app.workers.ai_worker`) nas chamadas ao assistente de
IA — sobrepõe, quando presente, os valores default vindos de variáveis de
ambiente (`app.core.config.Settings`). Ver
`app.services.ai_settings_service.get_effective_llm_config`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

SINGLETON_ID = "singleton"


class AiSettings(Base):
    """Configuração do assistente de IA, editável via `/admin/ai-settings`."""

    __tablename__ = "ai_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=SINGLETON_ID)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:  # pragma: no cover - apenas debug
        return f"AiSettings(id={self.id!r}, model={self.model!r})"
