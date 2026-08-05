"""Hashing de senha e emissão/validação de JWT (RF02, RF03, RNF01).

Convenções dos claims do JWT usados neste projeto:
- `sub`: id do usuário (str, UUID).
- `role`: papel do usuário (`"admin"` | `"editor"`).
- `type`: `"access"` ou `"refresh"`, para impedir que um refresh token seja
  aceito como access token (ou vice-versa) em `app.api.deps.get_current_user`.
- `jti`: identificador único do token, usado pela blacklist de refresh token
  (RF06, `app.services.token_blacklist`).
- `iat` / `exp`: emissão e expiração padrão do JWT.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro (RNF01)."""

    return str(_pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica se `plain` corresponde ao hash `hashed`."""

    return bool(_pwd_context.verify(plain, hashed))


def _jsonable(value: Any) -> Any:
    """Converte valores não serializáveis (ex.: `UserRole`) para JSON puro."""

    if isinstance(value, Enum):
        return value.value
    return value


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Cria um JWT assinado a partir de `data`.

    Apesar do nome (mantido conforme o contrato de módulos exigido pela
    SPEC-001), esta função é reutilizada tanto para o access token (60 min)
    quanto para o refresh token (7 dias) — o chamador diferencia os dois via
    claim `"type"` e `expires_delta`.
    """

    settings = get_settings()
    to_encode: dict[str, Any] = {key: _jsonable(value) for key, value in data.items()}

    now = datetime.now(UTC)
    delta = (
        expires_delta if expires_delta is not None else timedelta(minutes=settings.jwt_expires_min)
    )
    expire = now + delta

    to_encode.setdefault("jti", str(uuid.uuid4()))
    to_encode["iat"] = now
    to_encode["exp"] = expire

    return str(jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica e valida um JWT, retornando seus claims.

    Levanta `jose.exceptions.JWTError` (ou subclasses, ex.:
    `ExpiredSignatureError`) se o token for inválido, expirado ou malformado.
    Cabe ao chamador (ex.: `app.api.deps.get_current_user`) traduzir isso em
    um `401`.
    """

    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return payload
