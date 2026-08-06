"""Client da API de LLM (SPEC-003 — Assistente de IA para Redação de Posts).

`AiClient` (Protocol) é a interface consumida por
`app.services.ai_assistant_service.process_job`. Em testes unitários,
`get_ai_client` é sempre substituída via `app.dependency_overrides` por um
fake 100% em memória (`FakeAiClient`, em
`tests/unit/test_ai_assistant_service_spec003.py`) — nenhum teste chama a
API de LLM real (`specs/TESTING.md`).

Duas implementações de produção, uma por provedor (SPEC-004 — configurável
via `/admin/ai-settings`, campo `provider`):

- `HttpAiClient`: Anthropic Messages API (`https://api.anthropic.com/v1/messages`).
- `GeminiAiClient`: Google Gemini API
  (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`).

Ambas testadas via `httpx.MockTransport` (parâmetro `transport`, usado
apenas em teste — em produção nunca é passado, e o `httpx.AsyncClient`
interno usa seu transporte real). `build_ai_client` (chamada pelo worker,
`app.workers.ai_worker.run_worker`) escolhe a implementação certa a partir
de `app.services.ai_settings_service.LlmConfig.provider`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.ai_settings_service import LlmConfig


class AiClientError(Exception):
    """Erro de comunicação com a API da LLM.

    Levantada tanto para falha/timeout da chamada HTTP (RNF01: timeout de
    30s) quanto para uma resposta que não pôde ser interpretada como JSON
    estruturado — quem chama (`process_job`) trata ambos os casos da mesma
    forma: marca o job como `failed` com uma mensagem genérica (RNF02),
    nunca propagando o detalhe interno da exceção.
    """


@dataclass(frozen=True)
class AiUsage:
    """Uso de tokens de uma chamada à LLM (RNF04 — custo/uso deve ser logado).

    `app.services.ai_assistant_service.process_job` loga estes números (via
    `logging`, nível INFO) para cada job processado, nunca o conteúdo do
    prompt/resposta em texto plano.
    """

    tokens_input: int
    tokens_output: int


@dataclass(frozen=True)
class AiGenerationResult:
    """Retorno de `AiClient.generate`.

    `data` é o JSON estruturado decodificado (ainda não validado contra
    `app.schemas.ai_assistant.GeneratedDraftResult`); `usage` é o uso de
    tokens da chamada (RNF04).
    """

    data: dict[str, object]
    usage: AiUsage


class AiClient(Protocol):
    """Interface que qualquer implementação de client de LLM deve satisfazer."""

    async def generate(self, system_prompt: str, user_message: str) -> AiGenerationResult:
        """Chama a LLM e retorna o JSON estruturado decodificado (ainda não
        validado) junto com o uso de tokens da chamada (RNF04).

        Implementações devem levantar `AiClientError` em caso de
        timeout/erro de rede/erro HTTP, ou se a resposta não puder ser
        interpretada como um objeto JSON.
        """
        ...


#: Versão da Anthropic Messages API exigida em toda chamada (header
#: `anthropic-version`) — sem ela a API responde 400 antes mesmo de
#: considerar o restante do payload. Ver skill `claude-api` (curl/examples.md
#: § Required Headers).
_ANTHROPIC_API_VERSION = "2023-06-01"


class HttpAiClient:
    """Implementação de produção de `AiClient` — chama a Anthropic Messages API.

    Formato de resposta: `content: [{"type": "text", "text": "<json>"}]`,
    `usage: {"input_tokens": int, "output_tokens": int}` (ver
    `_extract_json_content`/`_extract_usage`).
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: int,
        max_output_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        # Uso exclusivo em teste (`tests/unit/test_ai_client_spec003.py`, via
        # `httpx.MockTransport`) — em produção `get_ai_client()` nunca passa
        # `transport`, então `httpx.AsyncClient` usa seu transporte real.
        self._transport = transport

    async def generate(self, system_prompt: str, user_message: str) -> AiGenerationResult:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    self._base_url,
                    headers={
                        "x-api-key": self._api_key or "",
                        "anthropic-version": _ANTHROPIC_API_VERSION,
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_message}],
                        # C2 (ai-safety-reviewer): teto de tokens de saída —
                        # sem isso o custo por chamada é ilimitado (RF07 só
                        # limita o número de chamadas/hora, não seu tamanho).
                        "max_tokens": self._max_output_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AiClientError("Timeout ao chamar a API da LLM.") from exc
        except httpx.HTTPError as exc:
            raise AiClientError("Erro ao chamar a API da LLM.") from exc

        parsed = _extract_json_content(data)
        if parsed is None:
            raise AiClientError("Resposta da LLM não pôde ser interpretada como JSON.")
        return AiGenerationResult(data=parsed, usage=_extract_usage(data))


#: Gemini não versiona a API via header (ao contrário da Anthropic) — a
#: versão vai no próprio path (`v1beta`), incluída em `llm_api_base_url`.
_GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAiClient:
    """Implementação de produção de `AiClient` — chama a Google Gemini API.

    Endpoint: `POST {base_url}/{model}:generateContent`, autenticado via
    header `x-goog-api-key` (não `x-api-key`/Bearer). Formato de
    request/response distinto do estilo Anthropic Messages API: o prompt de
    sistema vai em `system_instruction.parts[].text` (não em `system`), a
    mensagem do usuário em `contents[].parts[].text`, e o teto de tokens de
    saída em `generationConfig.maxOutputTokens` (não `max_tokens`). Ver
    https://ai.google.dev/gemini-api/docs/generate-content/text-generation.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: int,
        max_output_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        # Uso exclusivo em teste — ver docstring do módulo.
        self._transport = transport

    async def generate(self, system_prompt: str, user_message: str) -> AiGenerationResult:
        url = f"{self._base_url.rstrip('/')}/{self._model}:generateContent"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self._api_key or "",
                        "content-type": "application/json",
                    },
                    json={
                        "system_instruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                        # C2 (ai-safety-reviewer, ver HttpAiClient): mesmo
                        # teto de tokens de saída, campo equivalente na
                        # Gemini API.
                        "generationConfig": {"maxOutputTokens": self._max_output_tokens},
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AiClientError("Timeout ao chamar a API da LLM.") from exc
        except httpx.HTTPError as exc:
            raise AiClientError("Erro ao chamar a API da LLM.") from exc

        parsed = _extract_gemini_json_content(data)
        if parsed is None:
            raise AiClientError("Resposta da LLM não pôde ser interpretada como JSON.")
        return AiGenerationResult(data=parsed, usage=_extract_gemini_usage(data))


def build_ai_client(
    config: LlmConfig, *, transport: httpx.AsyncBaseTransport | None = None
) -> AiClient:
    """Constrói o client de produção certo a partir de `config.provider` (SPEC-004).

    Única função que decide "Anthropic ou Gemini" — chamada pelo worker
    (`app.workers.ai_worker.run_worker`) a cada ciclo, com a configuração
    efetiva (banco + fallback de env) já resolvida por
    `app.services.ai_settings_service.get_effective_llm_config`.
    """

    if config.provider == "gemini":
        return GeminiAiClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            max_output_tokens=config.max_output_tokens,
            transport=transport,
        )

    return HttpAiClient(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
        max_output_tokens=config.max_output_tokens,
        transport=transport,
    )


def _extract_json_content(data: dict[str, object]) -> dict[str, object] | None:
    """Extrai e decodifica o JSON estruturado do corpo de resposta da LLM."""

    content = data.get("content")
    if not isinstance(content, list) or not content:
        return None

    first_block = content[0]
    if not isinstance(first_block, dict):
        return None

    text = first_block.get("text")
    if not isinstance(text, str):
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _extract_usage(data: dict[str, object]) -> AiUsage:
    """Extrai o uso de tokens do corpo de resposta da LLM (RNF04).

    Formato assumido estilo Anthropic Messages API (`usage: {"input_tokens":
    int, "output_tokens": int}`). Ausente/malformado é tratado como `0`
    (best-effort — nunca impede o processamento do job).
    """

    usage = data.get("usage")
    if not isinstance(usage, dict):
        return AiUsage(tokens_input=0, tokens_output=0)

    tokens_input = usage.get("input_tokens")
    tokens_output = usage.get("output_tokens")
    return AiUsage(
        tokens_input=tokens_input if isinstance(tokens_input, int) else 0,
        tokens_output=tokens_output if isinstance(tokens_output, int) else 0,
    )


def _extract_gemini_json_content(data: dict[str, object]) -> dict[str, object] | None:
    """Extrai e decodifica o JSON estruturado da resposta da Gemini API.

    Formato: `candidates[0].content.parts[0].text` (string contendo o JSON),
    análogo a `_extract_json_content` para o formato Anthropic.
    """

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None

    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        return None

    content = first_candidate.get("content")
    if not isinstance(content, dict):
        return None

    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        return None

    first_part = parts[0]
    if not isinstance(first_part, dict):
        return None

    text = first_part.get("text")
    if not isinstance(text, str):
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _extract_gemini_usage(data: dict[str, object]) -> AiUsage:
    """Extrai o uso de tokens da resposta da Gemini API (RNF04).

    Formato: `usageMetadata: {"promptTokenCount": int, "candidatesTokenCount":
    int}` — nomes de campo diferentes do formato Anthropic
    (`_extract_usage`), mesmo comportamento best-effort (ausente/malformado
    vira `0`, nunca impede o processamento do job).
    """

    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        return AiUsage(tokens_input=0, tokens_output=0)

    tokens_input = usage.get("promptTokenCount")
    tokens_output = usage.get("candidatesTokenCount")
    return AiUsage(
        tokens_input=tokens_input if isinstance(tokens_input, int) else 0,
        tokens_output=tokens_output if isinstance(tokens_output, int) else 0,
    )


_http_ai_client: HttpAiClient | None = None


def get_ai_client() -> AiClient:  # pragma: no cover - implementação de produção não testada
    """Dependency FastAPI: fornece o client de LLM.

    Override-ável em testes via
    `app.dependency_overrides[get_ai_client] = lambda: fake_instance`. Nunca
    instanciada nos testes unitários (sempre substituída por `FakeAiClient`
    via `dependency_overrides`) — ver docstring do módulo.
    """

    global _http_ai_client
    if _http_ai_client is None:
        settings = get_settings()
        _http_ai_client = HttpAiClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_api_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    return _http_ai_client
