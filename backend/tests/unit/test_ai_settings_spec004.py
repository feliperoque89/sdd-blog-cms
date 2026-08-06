"""Testes unitários — configuração da IA (SPEC-004).

Tela `/admin/ai-settings` permite sobrepor, em runtime, `model`/`base_url`/
`api_key`/`max_output_tokens`/`timeout_seconds` usados pelo worker
(`app.workers.ai_worker`) nas chamadas ao assistente de IA, sem depender só
de variáveis de ambiente.

Mapeamento:
- GET sem configuração salva -> cai no fallback de `Settings` (env).
- PUT cria/atualiza a configuração; resposta nunca inclui a chave em texto
  puro (`api_key_last4`/`api_key_set`).
- PUT com `api_key` omitida/vazia preserva a chave já salva.
- Autenticação obrigatória (401 sem sessão).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import get_settings
from app.schemas.ai_settings import AiSettingsInput
from app.services import ai_settings_service


async def test_get_ai_settings_falls_back_to_env_settings_when_unconfigured_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.get("/api/admin/ai-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["api_key_set"] is False
    assert body["api_key_last4"] is None
    # Vem do fallback de `Settings` (env de teste) — apenas confere que os
    # campos obrigatórios do contrato estão presentes e não vazios.
    assert body["model"]
    assert body["base_url"]
    # RF06: sem configuração salva nem override de env, o fallback é "anthropic".
    assert body["provider"] == "anthropic"


async def test_put_ai_settings_creates_and_masks_api_key_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "model": "claude-sonnet-5",
            "base_url": "https://api.anthropic.com/v1/messages",
            "api_key": "sk-ant-abcd1234",
            "max_output_tokens": 2048,
            "timeout_seconds": 25,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "claude-sonnet-5"
    assert body["base_url"] == "https://api.anthropic.com/v1/messages"
    assert body["max_output_tokens"] == 2048
    assert body["timeout_seconds"] == 25
    assert body["api_key_set"] is True
    assert body["api_key_last4"] == "1234"
    assert "api_key" not in body
    # provider omitido -> default "anthropic" (RF06).
    assert body["provider"] == "anthropic"


async def test_put_ai_settings_persists_gemini_provider_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
            "api_key": "AIza-test-key",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "gemini"

    get_response = await editor_client.get("/api/admin/ai-settings")
    assert get_response.json()["provider"] == "gemini"


async def test_put_ai_settings_rejects_unknown_provider_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "provider": "openai",
            "model": "gpt-5",
            "base_url": "https://api.openai.com/v1/chat/completions",
        },
    )

    assert response.status_code == 422


async def test_put_ai_settings_rejects_base_url_host_mismatched_with_provider_spec004(
    editor_client: AsyncClient,
) -> None:
    # Achado C4 (ai-safety-reviewer, auditoria SPEC-004): provider "gemini"
    # com base_url da Anthropic (ou qualquer host arbitrário) enviaria a
    # chave configurada para o host errado — precisa ser rejeitado antes de
    # persistir, não só na hora do worker chamar a LLM.
    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "base_url": "https://api.anthropic.com/v1/messages",
            "api_key": "AIza-test-key",
        },
    )

    assert response.status_code == 422


async def test_put_ai_settings_rejects_non_https_base_url_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "base_url": "http://api.anthropic.com/v1/messages",
        },
    )

    assert response.status_code == 422


async def test_get_ai_settings_reflects_saved_configuration_spec004(
    editor_client: AsyncClient,
) -> None:
    await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "model": "claude-opus-5",
            "base_url": "https://api.anthropic.com/v1/messages",
            "api_key": "sk-ant-wxyz9999",
        },
    )

    response = await editor_client.get("/api/admin/ai-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "claude-opus-5"
    assert body["api_key_last4"] == "9999"


async def test_put_ai_settings_without_api_key_preserves_existing_key_spec004(
    editor_client: AsyncClient,
) -> None:
    await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "model": "claude-sonnet-5",
            "base_url": "https://api.anthropic.com/v1/messages",
            "api_key": "sk-ant-original1",
        },
    )

    response = await editor_client.put(
        "/api/admin/ai-settings",
        json={
            "model": "claude-opus-5",
            "base_url": "https://api.anthropic.com/v1/messages",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "claude-opus-5"
    assert body["api_key_set"] is True
    assert body["api_key_last4"] == "nal1"  # últimos 4 de "sk-ant-original1"


async def test_get_ai_settings_without_authentication_returns_401_spec004(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/admin/ai-settings")

    assert response.status_code == 401


async def test_put_ai_settings_without_authentication_returns_401_spec004(
    client: AsyncClient,
) -> None:
    response = await client.put(
        "/api/admin/ai-settings",
        json={"model": "claude-opus-5", "base_url": "https://api.anthropic.com/v1/messages"},
    )

    assert response.status_code == 401


async def test_put_ai_settings_requires_model_and_base_url_spec004(
    editor_client: AsyncClient,
) -> None:
    response = await editor_client.put("/api/admin/ai-settings", json={})

    assert response.status_code == 422


async def test_get_effective_llm_config_falls_back_to_env_when_unconfigured_spec004(
    db_session,
) -> None:
    config = await ai_settings_service.get_effective_llm_config(db_session)

    assert config.model
    assert config.base_url
    assert config.timeout_seconds > 0
    assert config.max_output_tokens > 0
    assert config.provider == "anthropic"


async def test_get_effective_llm_config_uses_saved_settings_when_present_spec004(
    db_session,
) -> None:
    await ai_settings_service.save_ai_settings(
        db_session,
        AiSettingsInput(
            provider="gemini",
            model="claude-opus-5",
            base_url="https://generativelanguage.googleapis.com/v1beta/models",
            api_key="sk-ant-worker-key",
            max_output_tokens=1234,
            timeout_seconds=12,
        ),
    )

    config = await ai_settings_service.get_effective_llm_config(db_session)

    assert config.model == "claude-opus-5"
    assert config.api_key == "sk-ant-worker-key"
    assert config.max_output_tokens == 1234
    assert config.timeout_seconds == 12
    assert config.provider == "gemini"


def test_to_public_self_heals_base_url_when_env_provider_and_base_url_mismatch_spec004() -> None:
    # Achado C4 residual (ai-safety-reviewer, auditoria SPEC-004): o `PUT`
    # já rejeita provider/base_url incoerentes, mas `LLM_PROVIDER`/
    # `LLM_API_BASE_URL` (env) são configurados de forma independente e não
    # passam por essa validação — sem o self-heal em `to_public`, um deploy
    # com `LLM_PROVIDER=gemini` e `LLM_API_BASE_URL` ainda no default da
    # Anthropic mostraria (e o worker usaria) a chave da Gemini API contra o
    # host da Anthropic.
    mismatched_fallback = get_settings().model_copy(
        update={
            "llm_provider": "gemini",
            "llm_api_base_url": "https://api.anthropic.com/v1/messages",
        }
    )

    public = ai_settings_service.to_public(None, mismatched_fallback)

    assert public.provider == "gemini"
    assert public.base_url == "https://generativelanguage.googleapis.com/v1beta/models"


def test_to_public_self_heals_base_url_when_env_scheme_is_not_https_spec004() -> None:
    # Achado R11 (ai-safety-reviewer): o self-heal checava só o hostname, não
    # o scheme — um `LLM_API_BASE_URL` correto no host mas com `http://`
    # (erro de deploy) enviaria a `api_key` em texto claro.
    http_fallback = get_settings().model_copy(
        update={"llm_api_base_url": "http://api.anthropic.com/v1/messages"}
    )

    public = ai_settings_service.to_public(None, http_fallback)

    assert public.base_url == "https://api.anthropic.com/v1/messages"


async def test_get_effective_llm_config_self_heals_base_url_when_saved_row_predates_validation_spec004(
    db_session,
) -> None:
    # Mesma classe de achado, mas para uma linha do banco: simula uma
    # configuração gravada antes da validação de host existir (ou corrompida
    # fora da API) — `get_effective_llm_config` não pode repassar a
    # combinação incoerente para `build_ai_client`.
    from app.models.ai_settings import SINGLETON_ID, AiSettings

    db_session.add(
        AiSettings(
            id=SINGLETON_ID,
            provider="gemini",
            model="gemini-2.5-flash",
            base_url="https://api.anthropic.com/v1/messages",
            api_key="AIza-legacy-key",
        )
    )
    await db_session.commit()

    config = await ai_settings_service.get_effective_llm_config(db_session)

    assert config.provider == "gemini"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/models"
