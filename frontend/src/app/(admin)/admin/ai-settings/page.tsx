"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  getAiSettings,
  saveAiSettings,
  PROVIDER_DEFAULT_BASE_URLS,
  type LlmProvider,
} from "@/lib/ai-settings-client";

export default function AiSettingsPage() {
  const [provider, setProvider] = useState<LlmProvider>("anthropic");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiKeySet, setApiKeySet] = useState(false);
  const [apiKeyLast4, setApiKeyLast4] = useState<string | null>(null);
  const [maxOutputTokens, setMaxOutputTokens] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    getAiSettings()
      .then((settings) => {
        setProvider(settings.provider);
        setModel(settings.model);
        setBaseUrl(settings.base_url);
        setApiKeySet(settings.api_key_set);
        setApiKeyLast4(settings.api_key_last4);
        setMaxOutputTokens(settings.max_output_tokens?.toString() ?? "");
        setTimeoutSeconds(settings.timeout_seconds?.toString() ?? "");
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Não foi possível carregar a configuração da IA."
        );
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const updated = await saveAiSettings({
        provider,
        model,
        base_url: baseUrl,
        // Campo em branco preserva a chave já salva (ver AiSettingsInput).
        api_key: apiKey.trim() === "" ? undefined : apiKey.trim(),
        max_output_tokens: maxOutputTokens.trim() === "" ? null : Number(maxOutputTokens),
        timeout_seconds: timeoutSeconds.trim() === "" ? null : Number(timeoutSeconds),
      });
      setApiKeySet(updated.api_key_set);
      setApiKeyLast4(updated.api_key_last4);
      setApiKey("");
      setSuccessMessage("Configuração salva com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar a configuração.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <p className="text-sm text-gray-600">Carregando configuração...</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Configuração do assistente de IA</h1>
      <p className="text-sm text-gray-600">
        Estes valores são usados nas chamadas do worker à API da LLM (assistente de IA da
        SPEC-003). Quando não configurados aqui, o backend usa os valores padrão do ambiente.
      </p>

      <form onSubmit={handleSubmit} className="flex max-w-xl flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="ai-settings-provider" className="text-sm font-medium text-foreground">
            Provider
          </label>
          <select
            id="ai-settings-provider"
            name="provider"
            value={provider}
            onChange={(event) => {
              const nextProvider = event.target.value as LlmProvider;
              setProvider(nextProvider);
              // O backend só aceita o host oficial de cada provider (RF06) —
              // ao trocar, já preenche o base_url correspondente.
              setBaseUrl(PROVIDER_DEFAULT_BASE_URLS[nextProvider]);
            }}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Google Gemini</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-settings-model" className="text-sm font-medium text-foreground">
            Model
          </label>
          <input
            id="ai-settings-model"
            name="model"
            type="text"
            required
            value={model}
            onChange={(event) => setModel(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-settings-base-url" className="text-sm font-medium text-foreground">
            Base URL
          </label>
          <input
            id="ai-settings-base-url"
            name="base_url"
            type="text"
            required
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-settings-api-key" className="text-sm font-medium text-foreground">
            API Key{" "}
            {apiKeySet ? (
              <span className="font-normal text-gray-500">
                (atual termina em {apiKeyLast4})
              </span>
            ) : (
              <span className="font-normal text-gray-500">(não configurada)</span>
            )}
          </label>
          <input
            id="ai-settings-api-key"
            name="api_key"
            type="password"
            autoComplete="off"
            placeholder={apiKeySet ? "Deixe em branco para manter a chave atual" : "sk-ant-..."}
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="ai-settings-max-output-tokens"
            className="text-sm font-medium text-foreground"
          >
            Máximo de tokens de saída
          </label>
          <input
            id="ai-settings-max-output-tokens"
            name="max_output_tokens"
            type="number"
            min={1}
            value={maxOutputTokens}
            onChange={(event) => setMaxOutputTokens(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="ai-settings-timeout-seconds"
            className="text-sm font-medium text-foreground"
          >
            Timeout (segundos)
          </label>
          <input
            id="ai-settings-timeout-seconds"
            name="timeout_seconds"
            type="number"
            min={1}
            value={timeoutSeconds}
            onChange={(event) => setTimeoutSeconds(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        {successMessage && <p className="text-sm text-green-700">{successMessage}</p>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Salvar
        </button>
      </form>
    </div>
  );
}
