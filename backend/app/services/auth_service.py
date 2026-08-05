"""Regra de negócio de autenticação (SPEC-001).

Router (`app.api.auth`) fica responsável apenas por HTTP (status codes,
cookies); toda a lógica de negócio — validação de credenciais, rate limit,
emissão de tokens e invalidação de refresh token no logout — vive aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.models.user import User
from app.services.rate_limiter import LoginRateLimiter
from app.services.token_blacklist import TokenBlacklist


class InvalidCredentialsError(Exception):
    """E-mail inexistente, senha incorreta ou usuário inativo (RF01/RF02)."""


class RateLimitExceededError(Exception):
    """Limite de tentativas de login excedido para a chave informada (RNF02)."""


@dataclass(frozen=True)
class TokenPair:
    """Par de tokens (access + refresh) emitido após um login bem-sucedido."""

    access_token: str
    refresh_token: str
    access_token_expires_seconds: int
    refresh_token_expires_seconds: int


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Busca um usuário pelo e-mail (case-sensitive, conforme armazenado)."""

    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate(
    db: AsyncSession,
    rate_limiter: LoginRateLimiter,
    client_key: str,
    email: str,
    password: str,
) -> User:
    """Valida credenciais de login, respeitando o rate limit (RNF02).

    Levanta `RateLimitExceededError` se o limite de tentativas para
    `client_key` (tipicamente o IP do cliente) tiver sido excedido, ou
    `InvalidCredentialsError` se e-mail/senha não corresponderem a um
    usuário ativo cadastrado.
    """

    if not await rate_limiter.is_allowed(client_key):
        raise RateLimitExceededError()

    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise InvalidCredentialsError()

    if not security.verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    return user


def issue_tokens(user: User) -> TokenPair:
    """Emite o par de tokens (access 60min / refresh 7 dias) para `user` (RF03)."""

    settings = get_settings()
    access_expires_delta = timedelta(minutes=settings.jwt_expires_min)
    refresh_expires_delta = timedelta(days=settings.jwt_refresh_expires_days)

    access_token = security.create_access_token(
        data={"sub": user.id, "role": user.role, "type": "access"},
        expires_delta=access_expires_delta,
    )
    refresh_token = security.create_access_token(
        data={"sub": user.id, "role": user.role, "type": "refresh"},
        expires_delta=refresh_expires_delta,
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_seconds=int(access_expires_delta.total_seconds()),
        refresh_token_expires_seconds=int(refresh_expires_delta.total_seconds()),
    )


async def logout(blacklist: TokenBlacklist, refresh_token: str | None) -> None:
    """Invalida o refresh token (RF06), adicionando seu `jti` à blacklist.

    Silenciosamente ignora tokens ausentes/inválidos: logout deve sempre
    limpar os cookies do lado do cliente (feito pelo router), mesmo que não
    haja refresh token válido para invalidar no servidor.
    """

    if not refresh_token:
        return

    try:
        payload = security.decode_token(refresh_token)
    except JWTError:
        return

    jti = payload.get("jti")
    if jti is None:
        return

    exp = payload.get("exp")
    ttl_seconds = 1
    if exp is not None:
        remaining = int(exp - datetime.now(UTC).timestamp())
        ttl_seconds = max(remaining, 1)

    await blacklist.add(jti, ttl_seconds=ttl_seconds)
