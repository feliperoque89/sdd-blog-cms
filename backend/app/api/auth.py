"""Router de autenticação (SPEC-001) — `POST/GET /api/auth/*`.

Apenas orquestração HTTP (parsing de request, cookies, status codes); toda a
regra de negócio vive em `app.services.auth_service`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, UserPublic
from app.services import auth_service
from app.services.rate_limiter import LoginRateLimiter, get_login_rate_limiter
from app.services.token_blacklist import TokenBlacklist, get_token_blacklist

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

# RNF03 exige `SameSite=Strict` (case sensível, ver testes de SPEC-001).
# Starlette tipa `samesite` como `Literal["lax", "strict", "none"]`
# (minúsculo) mas não normaliza o valor — em runtime aceita qualquer str,
# por isso usamos "Strict" (maiúsculo) com `type: ignore[arg-type]` abaixo.


def _set_auth_cookies(response: Response, tokens: auth_service.TokenPair) -> None:
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=tokens.access_token,
        max_age=tokens.access_token_expires_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Strict",  # type: ignore[arg-type]
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=tokens.refresh_token,
        max_age=tokens.refresh_token_expires_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Strict",  # type: ignore[arg-type]
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Strict",  # type: ignore[arg-type]
    )
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Strict",  # type: ignore[arg-type]
    )


@router.post("/login", response_model=UserPublic, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    rate_limiter: LoginRateLimiter = Depends(get_login_rate_limiter),
) -> UserPublic:
    """`POST /api/auth/login` — RF01/RF02. Ver `specs/features/SPEC-001-auth.md`."""

    client_key = request.client.host if request.client else "unknown"

    try:
        user = await auth_service.authenticate(
            db=db,
            rate_limiter=rate_limiter,
            client_key=client_key,
            email=payload.email,
            password=payload.password,
        )
    except auth_service.RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente em instantes.",
        ) from exc
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        ) from exc

    tokens = auth_service.issue_tokens(user)
    _set_auth_cookies(response, tokens)

    return UserPublic.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> None:
    """`POST /api/auth/logout` — RF06: invalida o refresh token e limpa cookies."""

    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    await auth_service.logout(blacklist, refresh_token)
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserPublic, status_code=status.HTTP_200_OK)
async def me(user: User = Depends(get_current_user)) -> UserPublic:
    """`GET /api/auth/me` — dados do usuário autenticado (`401` caso contrário)."""

    return UserPublic.model_validate(user)
