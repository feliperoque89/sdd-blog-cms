/**
 * Cliente HTTP fino para a configuração do assistente de IA (SPEC-004).
 * Mesmo espírito de `api-client.ts`/`posts-client.ts`.
 */

import { getApiBaseUrl } from "./api-base-url";

/** Provedores de LLM suportados (SPEC-004 / RF06). */
export type LlmProvider = "anthropic" | "gemini";

/**
 * `base_url` default por provider — o backend só aceita o host oficial de
 * cada provider (achado C4 do ai-safety-reviewer: provider/base_url
 * incoerentes enviam a chave configurada para o host errado), então a tela
 * preenche automaticamente o valor correto ao trocar o provider.
 */
export const PROVIDER_DEFAULT_BASE_URLS: Record<LlmProvider, string> = {
  anthropic: "https://api.anthropic.com/v1/messages",
  gemini: "https://generativelanguage.googleapis.com/v1beta/models",
};

export interface AiSettingsPublic {
  provider: LlmProvider;
  model: string;
  base_url: string;
  api_key_last4: string | null;
  api_key_set: boolean;
  max_output_tokens: number | null;
  timeout_seconds: number | null;
}

export interface AiSettingsInput {
  provider: LlmProvider;
  model: string;
  base_url: string;
  /** Omitido/`undefined` preserva a chave já salva no backend. */
  api_key?: string;
  max_output_tokens?: number | null;
  timeout_seconds?: number | null;
}

const API_URL = getApiBaseUrl();

interface ErrorBody {
  detail?: string;
}

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as ErrorBody;
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function getAiSettings(): Promise<AiSettingsPublic> {
  const response = await fetch(`${API_URL}/api/admin/ai-settings`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Não foi possível carregar a configuração da IA.")
    );
  }

  return (await response.json()) as AiSettingsPublic;
}

export async function saveAiSettings(input: AiSettingsInput): Promise<AiSettingsPublic> {
  const response = await fetch(`${API_URL}/api/admin/ai-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, "Não foi possível salvar a configuração da IA.")
    );
  }

  return (await response.json()) as AiSettingsPublic;
}
