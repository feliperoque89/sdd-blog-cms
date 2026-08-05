"""Ponto de entrada da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_assistant import router as ai_assistant_router
from app.api.auth import router as auth_router
from app.api.posts_admin import router as posts_admin_router
from app.api.posts_public import router as posts_public_router
from app.core.config import get_settings

app = FastAPI(title="SDD Blog CMS API")

# SPEC-001: frontend e backend rodam em origens diferentes (Next.js dev
# server / container `frontend` vs. `backend`) e a autenticação depende de
# cookies httpOnly — `allow_credentials=True` exige uma lista explícita de
# origens (nunca "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ai_assistant_router)
app.include_router(posts_admin_router)
app.include_router(posts_public_router)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Healthcheck simples, usado por orquestração de containers."""

    return {"status": "ok"}
