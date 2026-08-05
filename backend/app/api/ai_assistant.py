"""Router do assistente de IA (SPEC-003) — `/api/posts/generate-draft*`.

Apenas orquestração HTTP (parsing de request, status codes); toda a regra de
negócio vive em `app.services.ai_assistant_service`. Todas as rotas exigem
autenticação com papel `editor` ou `admin` (RF01). RF02: `POST` nunca aguarda
a LLM responder, só enfileira o job e retorna `202` imediatamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.models.assistant_draft import JobStatus
from app.models.user import User
from app.schemas.ai_assistant import (
    GeneratedDraftResult,
    GenerateDraftAccepted,
    GenerateDraftRequest,
    JobStatusResponse,
)
from app.services import ai_assistant_service
from app.services.ai_assistant_service import (
    AiRateLimiter,
    JobQueue,
    get_ai_rate_limiter,
    get_job_queue,
)

router = APIRouter(prefix="/api/posts", tags=["ai-assistant"])

_JOB_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Job de geração não encontrado."
)


@router.post(
    "/generate-draft",
    response_model=GenerateDraftAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_draft(
    payload: GenerateDraftRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("editor", "admin")),
    rate_limiter: AiRateLimiter = Depends(get_ai_rate_limiter),
    job_queue: JobQueue = Depends(get_job_queue),
) -> GenerateDraftAccepted:
    """`POST /api/posts/generate-draft` — RF01/RF02/RF06/RF07. `429` se rate limited."""

    try:
        job = await ai_assistant_service.create_generation_job(
            db,
            editor_id=user.id,
            payload=payload,
            rate_limiter=rate_limiter,
            job_queue=job_queue,
        )
    except ai_assistant_service.AiRateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de gerações de IA excedido. Tente novamente mais tarde.",
        ) from exc

    return GenerateDraftAccepted(job_id=job.id, status=job.status)


@router.get("/generate-draft/{job_id}", response_model=JobStatusResponse)
async def get_generate_draft_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("editor", "admin")),
) -> JobStatusResponse:
    """`GET /api/posts/generate-draft/{job_id}` — RF05.

    `404` se `job_id` não existir OU se existir mas pertencer a outro editor
    (R1 — autorização em nível de objeto: editor só vê os próprios jobs,
    admin vê qualquer job; nunca `403`, para não confirmar a terceiros a
    existência de um job de outro usuário).
    """

    job = await ai_assistant_service.get_job_status_for_user(db, job_id, user=user)
    if job is None:
        raise _JOB_NOT_FOUND

    result: GeneratedDraftResult | None = None
    if job.status == JobStatus.DONE:
        result = GeneratedDraftResult(
            title=job.result_title or "",
            content_markdown=job.result_content_markdown or "",
            meta_description=job.result_meta_description or "",
            tags=job.result_tags or [],
        )

    return JobStatusResponse(job_id=job.id, status=job.status, result=result, error=job.error)
