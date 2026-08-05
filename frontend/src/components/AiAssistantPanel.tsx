"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  generateDraft,
  getDraftJobStatus,
  type AssistantDraftResult,
  type DraftLength,
  type DraftTone,
} from "@/lib/ai-assistant-client";

export interface AiAssistantPanelProps {
  onDraftReady?: (result: AssistantDraftResult) => void;
}

// A spec (SPEC-003) não define o intervalo exato de polling — assumimos
// 2000ms (ver nota em AiAssistantPanel.test.tsx). Consultamos o status uma
// primeira vez imediatamente ao receber o job_id (para não fazer o editor
// esperar um ciclo inteiro à toa) e, enquanto pendente, repetimos a cada
// POLL_INTERVAL_MS.
const POLL_INTERVAL_MS = 2000;

// Quantidade de caracteres do conteúdo markdown exibidos como preview antes
// de o editor decidir usar o rascunho (o conteúdo completo é sempre
// preservado no objeto passado a `onDraftReady`).
const CONTENT_PREVIEW_LENGTH = 300;

const GENERIC_ERROR_MESSAGE = "Não foi possível gerar o rascunho. Tente novamente mais tarde.";

function parseKeywords(keywordsInput: string): string[] {
  return keywordsInput
    .split(",")
    .map((keyword) => keyword.trim())
    .filter((keyword) => keyword.length > 0);
}

export default function AiAssistantPanel({ onDraftReady }: AiAssistantPanelProps) {
  const [topic, setTopic] = useState("");
  const [tone, setTone] = useState<DraftTone>("formal");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [length, setLength] = useState<DraftLength>("medium");

  const [jobId, setJobId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<AssistantDraftResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Polling do status do job enquanto `pending` for true. Reinicia sempre
  // que um novo job é criado e para (limpando o intervalo) assim que o job
  // sai do estado pending ou o componente desmonta.
  useEffect(() => {
    if (!jobId || !pending) {
      return;
    }

    let cancelled = false;

    function poll() {
      getDraftJobStatus(jobId as string)
        .then((status) => {
          if (cancelled) {
            return;
          }

          if (status.status === "done") {
            setResult(status.result ?? null);
            setPending(false);
          } else if (status.status === "failed") {
            setError(status.error ?? GENERIC_ERROR_MESSAGE);
            setPending(false);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) {
            return;
          }
          setError(err instanceof Error ? err.message : GENERIC_ERROR_MESSAGE);
          setPending(false);
        });
    }

    poll();
    const intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [jobId, pending]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError(null);
    setResult(null);

    try {
      const response = await generateDraft({
        topic,
        tone,
        keywords: parseKeywords(keywordsInput),
        length,
      });
      setJobId(response.job_id);
      setPending(true);
    } catch (err) {
      setPending(false);
      setError(err instanceof Error ? err.message : GENERIC_ERROR_MESSAGE);
    }
  }

  const contentPreview =
    result && result.content_markdown.length > CONTENT_PREVIEW_LENGTH
      ? `${result.content_markdown.slice(0, CONTENT_PREVIEW_LENGTH)}...`
      : result?.content_markdown;

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="ai-assistant-topic" className="text-sm font-medium text-foreground">
            Tópico
          </label>
          <textarea
            id="ai-assistant-topic"
            name="topic"
            required
            rows={3}
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-assistant-tone" className="text-sm font-medium text-foreground">
            Tom
          </label>
          <select
            id="ai-assistant-tone"
            name="tone"
            value={tone}
            onChange={(event) => setTone(event.target.value as DraftTone)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="formal">Formal</option>
            <option value="casual">Casual</option>
            <option value="tecnico">Técnico</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-assistant-keywords" className="text-sm font-medium text-foreground">
            Palavras-chave (separadas por vírgula)
          </label>
          <input
            id="ai-assistant-keywords"
            name="keywords"
            type="text"
            value={keywordsInput}
            onChange={(event) => setKeywordsInput(event.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="ai-assistant-length" className="text-sm font-medium text-foreground">
            Tamanho
          </label>
          <select
            id="ai-assistant-length"
            name="length"
            value={length}
            onChange={(event) => setLength(event.target.value as DraftLength)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="short">Curto</option>
            <option value="medium">Médio</option>
            <option value="long">Longo</option>
          </select>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Gerar rascunho
        </button>

        {pending && <p className="text-sm text-gray-600">Gerando rascunho, aguarde...</p>}
      </form>

      {result && (
        <div className="flex flex-col gap-2 rounded border border-gray-200 p-4">
          <h3 className="text-lg font-semibold text-foreground">{result.title}</h3>
          <p className="text-sm text-gray-600">{result.meta_description}</p>
          <div className="flex flex-wrap gap-2">
            {result.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700"
              >
                {tag}
              </span>
            ))}
          </div>
          <p className="whitespace-pre-wrap text-sm text-foreground">{contentPreview}</p>
          <button
            type="button"
            onClick={() => onDraftReady?.(result)}
            className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white"
          >
            Usar este rascunho
          </button>
        </div>
      )}
    </div>
  );
}
