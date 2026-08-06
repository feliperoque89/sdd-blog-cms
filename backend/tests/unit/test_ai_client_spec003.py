"""Testes unitários — `app.services.ai_client.HttpAiClient` (SPEC-003).

A auditoria de segurança (`ai-safety-reviewer`) identificou que o
`HttpAiClient` de produção não incluía o header `anthropic-version`,
exigido pela Anthropic Messages API (sem ele, toda chamada real recebe
400 antes mesmo de a saída ser validada — achado R6). Este arquivo
cobre o cliente HTTP real via `httpx.MockTransport`, sem chamar a API
de verdade (`specs/TESTING.md`).
"""

from __future__ import annotations

import httpx
import pytest

from app.services.ai_client import AiClientError, GeminiAiClient, HttpAiClient, build_ai_client
from app.services.ai_settings_service import LlmConfig

pytestmark = pytest.mark.asyncio

_BASE_URL = "https://api.anthropic.com/v1/messages"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _make_client(handler) -> HttpAiClient:
    return HttpAiClient(
        api_key="sk-ant-test-key",
        model="claude-sonnet-4-6",
        base_url=_BASE_URL,
        timeout_seconds=30,
        max_output_tokens=4096,
        transport=httpx.MockTransport(handler),
    )


def _make_gemini_client(handler) -> GeminiAiClient:
    return GeminiAiClient(
        api_key="AIza-test-key",
        model="gemini-2.5-flash",
        base_url=_GEMINI_BASE_URL,
        timeout_seconds=30,
        max_output_tokens=4096,
        transport=httpx.MockTransport(handler),
    )


def _make_llm_config(*, provider: str) -> LlmConfig:
    return LlmConfig(
        provider=provider,
        api_key="test-key",
        model="test-model",
        base_url=_BASE_URL,
        timeout_seconds=30,
        max_output_tokens=4096,
    )


async def test_generate_sends_required_anthropic_headers_spec003() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"title": "t"}'}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    client = _make_client(handler)
    await client.generate("system prompt", "user message")

    assert captured["x-api-key"] == "sk-ant-test-key"
    assert captured["anthropic-version"] == "2023-06-01"
    assert captured["content-type"] == "application/json"


async def test_generate_sends_expected_request_body_shape_spec003() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        import json as _json

        captured_body = _json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "{}"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = _make_client(handler)
    await client.generate("system prompt", "user message")

    assert captured_body["model"] == "claude-sonnet-4-6"
    assert captured_body["system"] == "system prompt"
    assert captured_body["messages"] == [{"role": "user", "content": "user message"}]
    assert captured_body["max_tokens"] == 4096


async def test_generate_parses_content_and_usage_from_response_spec003() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"title": "Como usar SDD"}'}],
                "usage": {"input_tokens": 42, "output_tokens": 17},
            },
        )

    client = _make_client(handler)
    result = await client.generate("system prompt", "user message")

    assert result.data == {"title": "Como usar SDD"}
    assert result.usage.tokens_input == 42
    assert result.usage.tokens_output == 17


async def test_generate_defaults_usage_to_zero_when_missing_spec003() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{}"}]})

    client = _make_client(handler)
    result = await client.generate("system prompt", "user message")

    assert result.usage.tokens_input == 0
    assert result.usage.tokens_output == 0


async def test_generate_raises_ai_client_error_on_http_error_status_spec003() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid x-api-key"}})

    client = _make_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


async def test_generate_raises_ai_client_error_on_timeout_spec003() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = _make_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


async def test_generate_raises_ai_client_error_on_malformed_json_text_spec003() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not valid json"}]})

    client = _make_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


# --- GeminiAiClient (SPEC-004 / RF06 — provider "gemini") ---------------------


async def test_gemini_generate_sends_expected_url_and_headers_spec004() -> None:
    captured: dict[str, str] = {}
    captured_url: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        captured_url["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"title": "t"}'}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
            },
        )

    client = _make_gemini_client(handler)
    await client.generate("system prompt", "user message")

    assert captured["x-goog-api-key"] == "AIza-test-key"
    assert captured["content-type"] == "application/json"
    assert captured_url["url"] == f"{_GEMINI_BASE_URL}/gemini-2.5-flash:generateContent"


async def test_gemini_generate_sends_expected_request_body_shape_spec004() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        import json as _json

        captured_body = _json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    client = _make_gemini_client(handler)
    await client.generate("system prompt", "user message")

    assert captured_body["system_instruction"] == {"parts": [{"text": "system prompt"}]}
    assert captured_body["contents"] == [{"role": "user", "parts": [{"text": "user message"}]}]
    assert captured_body["generationConfig"] == {"maxOutputTokens": 4096}


async def test_gemini_generate_parses_content_and_usage_from_response_spec004() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"title": "Como usar SDD"}'}]}}
                ],
                "usageMetadata": {"promptTokenCount": 42, "candidatesTokenCount": 17},
            },
        )

    client = _make_gemini_client(handler)
    result = await client.generate("system prompt", "user message")

    assert result.data == {"title": "Como usar SDD"}
    assert result.usage.tokens_input == 42
    assert result.usage.tokens_output == 17


async def test_gemini_generate_defaults_usage_to_zero_when_missing_spec004() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        )

    client = _make_gemini_client(handler)
    result = await client.generate("system prompt", "user message")

    assert result.usage.tokens_input == 0
    assert result.usage.tokens_output == 0


async def test_gemini_generate_raises_ai_client_error_on_http_error_status_spec004() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    client = _make_gemini_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


async def test_gemini_generate_raises_ai_client_error_on_timeout_spec004() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = _make_gemini_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


async def test_gemini_generate_raises_ai_client_error_on_malformed_json_text_spec004() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "not valid json"}]}}]}
        )

    client = _make_gemini_client(handler)
    with pytest.raises(AiClientError):
        await client.generate("system prompt", "user message")


# --- build_ai_client dispatch (SPEC-004 / RF06) -------------------------------


async def test_build_ai_client_returns_gemini_client_when_provider_is_gemini_spec004() -> None:
    client = build_ai_client(_make_llm_config(provider="gemini"))

    assert isinstance(client, GeminiAiClient)


async def test_build_ai_client_returns_http_client_when_provider_is_anthropic_spec004() -> None:
    client = build_ai_client(_make_llm_config(provider="anthropic"))

    assert isinstance(client, HttpAiClient)
