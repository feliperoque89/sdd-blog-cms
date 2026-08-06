"""Configuração da aplicação (variáveis de ambiente), via pydantic-settings.

Ver `specs/ARCHITECTURE.md` (seção "Variáveis de ambiente") para a lista de
variáveis suportadas em produção.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação, lidas de variáveis de ambiente (ou `.env`)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"

    # Banco de dados (SPEC-001 usa apenas `app.core.database`, mas a URL é
    # configurável para permitir MySQL em produção conforme ARCHITECTURE.md).
    database_url: str

    # Redis (blacklist de refresh token + rate limiter de login).
    redis_url: str

    # JWT (RF02/RF03).
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_min: int = 60
    jwt_refresh_expires_days: int = 7

    # Rate limit de login (RNF02).
    rate_limit_login_max_attempts: int = 5
    rate_limit_login_window_seconds: int = 60

    # Cookies (RNF03). `False` apenas em ambiente de teste/dev local sem TLS.
    cookie_secure: bool = True

    # CORS (SPEC-001): a origem do frontend precisa estar explicitamente
    # listada — cookies httpOnly cross-origin exigem `allow_credentials=True`,
    # que o navegador rejeita se combinado com `allow_origins=["*"]`. Sem
    # isso, nenhuma chamada do frontend (origem diferente do backend, ex.:
    # localhost:3000 -> localhost:8000) chega a sair do preflight OPTIONS.
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # LLM do assistente de IA (SPEC-003). Nenhum valor padrão sensível: em
    # produção, `LLM_API_KEY`/`LLM_MODEL` vêm de variáveis de ambiente (ver
    # specs/ARCHITECTURE.md). Nunca usados em testes unitários (a suíte
    # sempre faz override de `get_ai_client` por um fake).
    # Provedor da LLM (SPEC-004 / RF06): "anthropic" ou "gemini" — decide qual
    # implementação de `app.services.ai_client.AiClient` é usada
    # (`build_ai_client`). Sobreponível via `/admin/ai-settings`.
    llm_provider: str = "anthropic"
    llm_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-6"
    llm_api_base_url: str = "https://api.anthropic.com/v1/messages"
    llm_timeout_seconds: int = 30
    # Achado C2 (ai-safety-reviewer, auditoria SPEC-003): sem teto de tokens
    # de saída, uma chamada influenciada por prompt injection (ex.: "escreva
    # o texto mais longo possível") não tem limite de custo, mesmo com o
    # rate limit (RF07) limitando apenas o NÚMERO de chamadas por hora.
    llm_max_output_tokens: int = 4096

    # Rate limit de geração de rascunhos via IA (RF07 — 10 gerações/hora).
    rate_limit_ai_max_attempts: int = 10
    rate_limit_ai_window_seconds: int = 3600

    # Storage de mídia (SPEC-005 — upload de imagem de capa), MinIO
    # (S3-compatible, ver specs/ARCHITECTURE.md). Sem valor padrão, como
    # DATABASE_URL/REDIS_URL: exigido via ambiente/`.env`. Nunca usado em
    # testes unitários (a suíte sempre faz override de
    # `get_media_storage_client` por um fake).
    media_storage_endpoint_url: str
    media_storage_access_key: str
    media_storage_secret_key: str
    media_storage_bucket: str = "media"
    # Base pública usada para montar a URL devolvida ao cliente — pode
    # divergir de `media_storage_endpoint_url` (ex.: endpoint interno do
    # cluster vs. host exposto pelo Ingress).
    media_storage_public_base_url: str


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância (cacheada) de `Settings`.

    Usar sempre esta função em vez de instanciar `Settings()` diretamente,
    para reaproveitar o cache e permitir override fácil em testes, se
    necessário (`get_settings.cache_clear()`).
    """

    return Settings()
