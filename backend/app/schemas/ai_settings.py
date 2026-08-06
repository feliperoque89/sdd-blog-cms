"""Schemas Pydantic do contrato de API de configuração da IA (SPEC-004)."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

#: Provedores de LLM suportados (SPEC-004 / RF06) — decide qual implementação
#: de `app.services.ai_client.AiClient` é usada (`build_ai_client`).
LlmProvider = Literal["anthropic", "gemini"]

#: `base_url` oficial de cada provider (achado C3/C4 do ai-safety-reviewer,
#: auditoria SPEC-004: `provider`/`base_url`/`api_key` eram aceitos sem
#: nenhuma relação entre si, permitindo enviar a chave de um provider para o
#: host de outro, ou para um host arbitrário controlado por quem tem papel
#: `editor` — exfiltração de segredo/SSRF a partir do worker). Única fonte
#: da verdade de "qual host é válido para qual provider": usada tanto para
#: validar `PUT` (`_validate_base_url_matches_provider`) quanto para
#: recompor um `base_url` efetivo coerente em
#: `app.services.ai_settings_service` (inclusive quando vem do fallback de
#: env, que não passa por esta validação). Só os hosts oficiais de cada API
#: são aceitos; nada de proxy/gateway customizado (fora de escopo desta
#: spec).
PROVIDER_DEFAULT_BASE_URLS: dict[LlmProvider, str] = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
}


def provider_host(provider: LlmProvider) -> str:
    """Host esperado de `base_url` para `provider` (derivado de `PROVIDER_DEFAULT_BASE_URLS`)."""

    hostname = urlparse(PROVIDER_DEFAULT_BASE_URLS[provider]).hostname
    assert hostname is not None  # URLs fixas acima, sempre têm host.
    return hostname


class AiSettingsInput(BaseModel):
    """Payload de `PUT /api/admin/ai-settings`.

    `api_key`: se omitido ou vazio, a chave já armazenada é preservada — a
    tela nunca devolve a chave em texto puro (`GET`/`PUT` só retornam
    `api_key_last4`/`api_key_set`), então reenviar em branco é o único jeito
    de alterar os outros campos sem trocar a chave.
    """

    provider: LlmProvider = "anthropic"
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_base_url_matches_provider(self) -> AiSettingsInput:
        expected_host = provider_host(self.provider)
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname != expected_host:
            raise ValueError(
                f"base_url deve ser um endpoint https em {expected_host!r} "
                f"para provider={self.provider!r}."
            )
        return self


class AiSettingsPublic(BaseModel):
    """Resposta de `GET`/`PUT` — nunca inclui a chave de API em texto puro."""

    provider: LlmProvider
    model: str
    base_url: str
    api_key_last4: str | None = None
    api_key_set: bool
    max_output_tokens: int | None = None
    timeout_seconds: int | None = None
