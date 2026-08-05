"""Client da API de LLM (SPEC-003 — Assistente de IA para Redação de Posts).

`AiClient` (Protocol) é a interface consumida por
`app.services.ai_assistant_service.process_job`. Em testes unitários,
`get_ai_client` é sempre substituída via `app.dependency_overrides` por um
fake 100% em memória (`FakeAiClient`, em
`tests/unit/test_ai_assistant_service_spec003.py`) — nenhum teste chama a
API de LLM real (`specs/TESTING.md`).

`HttpAiClient` é a implementação de produção: um cliente HTTP genérico,
configurável via `LLM_API_KEY`/`LLM_MODEL` (`specs/ARCHITECTURE.md`). Por
orientação explícita da tarefa desta spec, ela não precisa funcionar de
verdade nem é exercitada por nenhum teste unitário (só existe como
implementação plausível por trás do protocol) — por isso o corpo dos seus
métodos é marcado com `# pragma: no cover`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings


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


class HttpAiClient:
    """Implementação de produção de `AiClient` via HTTP genérico.

    Assume um formato de resposta estilo Anthropic Messages API
    (`content: [{"type": "text", "text": "<json>"}]`) — ajustável conforme o
    provedor configurado em produção via `LLM_MODEL`. Nunca chamada em
    testes unitários (ver docstring do módulo).
    """

    def __init__(  # pragma: no cover - implementação de produção não testada
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: int,
        max_output_tokens: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    async def generate(  # pragma: no cover - implementação de produção não testada
        self, system_prompt: str, user_message: str
    ) -> AiGenerationResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    self._base_url,
                    headers={
                        "x-api-key": self._api_key or "",
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


def _extract_json_content(
    data: dict[str, object],
) -> dict[str, object] | None:  # pragma: no cover - implementação de produção não testada
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


def _extract_usage(
    data: dict[str, object],
) -> AiUsage:  # pragma: no cover - implementação de produção não testada
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
