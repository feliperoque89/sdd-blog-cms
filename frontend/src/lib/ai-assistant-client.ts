/**
 * Cliente HTTP fino para o assistente de IA de redação de posts (SPEC-003).
 * Mesmo espírito de `posts-client.ts`: nenhuma regra de negócio aqui, apenas
 * chamadas HTTP e parsing/erro de resposta. O prompt de sistema e a chamada
 * à LLM em si vivem inteiramente no backend (RNF02) — este módulo apenas
 * enfileira o job e consulta seu status.
 */

export type DraftTone = "formal" | "casual" | "tecnico";
export type DraftLength = "short" | "medium" | "long";

export interface GenerateDraftInput {
  topic: string;
  tone: DraftTone;
  keywords: string[];
  length: DraftLength;
}

export interface AssistantDraftResult {
  title: string;
  content_markdown: string;
  meta_description: string;
  tags: string[];
}

export type DraftJobState = "pending" | "done" | "failed";

export interface DraftJobStatus {
  job_id: string;
  status: DraftJobState;
  result?: AssistantDraftResult;
  error?: string;
}

export interface GenerateDraftResponse {
  job_id: string;
  status: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const RATE_LIMIT_MESSAGE = "Limite de gerações excedido, tente novamente mais tarde.";
const GENERIC_GENERATE_ERROR_MESSAGE = "Não foi possível gerar o rascunho. Tente novamente mais tarde.";
const GENERIC_STATUS_ERROR_MESSAGE = "Não foi possível consultar o status da geração.";

/**
 * POST /api/posts/generate-draft (auth: editor|admin). Response `202` com
 * `{ job_id, status: "pending" }` — o job é assíncrono, o worker chama a LLM
 * fora do ciclo de request/response (RF02).
 */
export async function generateDraft(input: GenerateDraftInput): Promise<GenerateDraftResponse> {
  const response = await fetch(`${API_URL}/api/posts/generate-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });

  if (response.status === 429) {
    throw new Error(RATE_LIMIT_MESSAGE);
  }

  if (!response.ok) {
    throw new Error(GENERIC_GENERATE_ERROR_MESSAGE);
  }

  return (await response.json()) as GenerateDraftResponse;
}

/**
 * GET /api/posts/generate-draft/{job_id} (auth: editor|admin). Usado para
 * polling do status do job até `done` ou `failed` (RF05).
 */
export async function getDraftJobStatus(jobId: string): Promise<DraftJobStatus> {
  const response = await fetch(`${API_URL}/api/posts/generate-draft/${encodeURIComponent(jobId)}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(GENERIC_STATUS_ERROR_MESSAGE);
  }

  return (await response.json()) as DraftJobStatus;
}
