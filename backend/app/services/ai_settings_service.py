"""Regra de negócio da configuração do assistente de IA (SPEC-004).

A tela `/admin/ai-settings` permite sobrepor, em runtime, os valores de
`model`/`base_url`/`api_key`/... que o worker (`app.workers.ai_worker`) usa
nas chamadas ao assistente de IA — sem isso, esses valores só podiam ser
trocados via variável de ambiente (`LLM_MODEL`/`LLM_API_KEY`/...), exigindo
reiniciar o worker/backend a cada troca. `get_effective_llm_config` é a
única função que o worker chama para montar o `HttpAiClient` de cada ciclo:
ela mescla o que estiver salvo em `AiSettings` (banco) com o default de
`Settings` (env) para qualquer campo não configurado no banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.ai_settings import SINGLETON_ID, AiSettings
from app.schemas.ai_settings import (
    PROVIDER_DEFAULT_BASE_URLS,
    AiSettingsInput,
    AiSettingsPublic,
    LlmProvider,
    provider_host,
)


@dataclass(frozen=True)
class LlmConfig:
    """Configuração efetiva de LLM usada por `build_ai_client` (mescla banco + env)."""

    provider: str
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: int
    max_output_tokens: int


def _normalize_provider(provider: str) -> LlmProvider:
    """Normaliza um `provider` de fonte não validada (banco/env) para `LlmProvider`.

    `AiSettingsInput` valida `provider` no `PUT`, mas o valor efetivo pode vir
    de `Settings.llm_provider` (env, `str` livre) ou de uma linha do banco
    gravada antes desta validação existir — qualquer valor que não seja
    exatamente `"gemini"` é tratado como `"anthropic"`, mesmo fallback que
    `app.services.ai_client.build_ai_client` já usa para decidir a
    implementação.
    """

    return "gemini" if provider == "gemini" else "anthropic"


def _effective_base_url(provider: str, configured: str | None, env_fallback: str) -> str:
    """`base_url` efetivo, corrigido para o host oficial de `provider` se necessário.

    Achado C4 (ai-safety-reviewer, auditoria SPEC-004): `PUT
    /api/admin/ai-settings` já rejeita `provider`/`base_url` incoerentes
    (`AiSettingsInput._validate_base_url_matches_provider`), mas essa
    validação não cobre o fallback de env (`Settings.llm_provider`/
    `llm_api_base_url`, configurados independentemente) nem uma linha
    gravada no banco antes da validação existir. Sem esta função, uma
    combinação como `LLM_PROVIDER=gemini` com `LLM_API_BASE_URL` ainda no
    default da Anthropic enviaria a `api_key` configurada para o host
    errado. Em vez de derrubar o worker, recompõe silenciosamente para o
    default oficial do provider.
    """

    normalized = _normalize_provider(provider)
    candidate = configured or env_fallback
    parsed = urlparse(candidate)
    if parsed.scheme == "https" and parsed.hostname == provider_host(normalized):
        return candidate
    return PROVIDER_DEFAULT_BASE_URLS[normalized]


async def get_ai_settings(db: AsyncSession) -> AiSettings | None:
    """Busca a linha singleton de configuração, se existir."""

    return await db.get(AiSettings, SINGLETON_ID)


async def save_ai_settings(db: AsyncSession, data: AiSettingsInput) -> AiSettings:
    """Cria ou atualiza a linha singleton de configuração.

    `api_key` vazio/omitido preserva a chave já armazenada (ver docstring de
    `AiSettingsInput`).
    """

    settings = await get_ai_settings(db)
    if settings is None:
        settings = AiSettings(id=SINGLETON_ID)
        db.add(settings)

    settings.provider = data.provider
    settings.model = data.model
    settings.base_url = data.base_url
    if data.api_key:
        settings.api_key = data.api_key
    settings.max_output_tokens = data.max_output_tokens
    settings.timeout_seconds = data.timeout_seconds

    await db.commit()
    await db.refresh(settings)
    return settings


def to_public(settings: AiSettings | None, fallback: Settings) -> AiSettingsPublic:
    """Converte para o contrato de resposta, mascarando `api_key`."""

    provider = _normalize_provider(
        (settings.provider if settings else None) or fallback.llm_provider
    )
    model = (settings.model if settings else None) or fallback.llm_model
    base_url = _effective_base_url(
        provider, settings.base_url if settings else None, fallback.llm_api_base_url
    )
    max_output_tokens = (
        settings.max_output_tokens if settings else None
    ) or fallback.llm_max_output_tokens
    timeout_seconds = (
        settings.timeout_seconds if settings else None
    ) or fallback.llm_timeout_seconds

    api_key = (settings.api_key if settings else None) or fallback.llm_api_key
    api_key_last4 = api_key[-4:] if api_key else None

    return AiSettingsPublic(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_last4=api_key_last4,
        api_key_set=bool(api_key),
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


async def get_effective_llm_config(db: AsyncSession) -> LlmConfig:
    """Configuração efetiva de LLM: banco (se configurado) com fallback para env.

    Chamada pelo worker (`app.workers.ai_worker.run_worker`) a cada ciclo,
    para que uma mudança salva via `/admin/ai-settings` valha na próxima
    geração sem precisar reiniciar o worker.
    """

    settings = await get_ai_settings(db)
    fallback = get_settings()

    provider = _normalize_provider(
        (settings.provider if settings else None) or fallback.llm_provider
    )

    return LlmConfig(
        provider=provider,
        api_key=(settings.api_key if settings else None) or fallback.llm_api_key,
        model=(settings.model if settings else None) or fallback.llm_model,
        base_url=_effective_base_url(
            provider, settings.base_url if settings else None, fallback.llm_api_base_url
        ),
        timeout_seconds=(settings.timeout_seconds if settings else None)
        or fallback.llm_timeout_seconds,
        max_output_tokens=(settings.max_output_tokens if settings else None)
        or fallback.llm_max_output_tokens,
    )
