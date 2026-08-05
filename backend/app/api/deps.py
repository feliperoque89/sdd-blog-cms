"""Dependencies FastAPI de autenticação/autorização (RF05).

- `get_current_user`: extrai e valida o access token do cookie httpOnly,
  retornando o `User` autenticado ou levantando `401`.
- `require_role`: factory de dependency que, além de exigir autenticação,
  exige que o usuário tenha um dos papéis informados, levantando `403`
  caso contrário.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.database import get_db
from app.models.user import User
from app.services.token_blacklist import TokenBlacklist, get_token_blacklist

ACCESS_TOKEN_COOKIE = "access_token"

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> User:
    """Resolve o usuário autenticado a partir do cookie `access_token`.

    Levanta `401` se o cookie estiver ausente, o token for malformado,
    estiver expirado, não for do tipo `"access"`, estiver na blacklist, ou
    não corresponder a um usuário ativo existente.
    """

    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise _UNAUTHENTICATED

    try:
        payload = security.decode_token(token)
    except JWTError as exc:
        raise _UNAUTHENTICATED from exc

    if payload.get("type") != "access":
        raise _UNAUTHENTICATED

    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTHENTICATED

    jti = payload.get("jti")
    if jti and await blacklist.is_blacklisted(jti):
        raise _UNAUTHENTICATED

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED

    return user


def require_role(*allowed_roles: str) -> Callable[..., Awaitable[User]]:
    """Factory de dependency FastAPI que restringe o acesso por papel (RF05).

    Uso: `Depends(require_role("admin"))`.
    """

    async def _require_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação.",
            )
        return user

    return _require_role
