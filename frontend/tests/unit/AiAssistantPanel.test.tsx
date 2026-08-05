import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { AssistantDraftResult } from "@/lib/ai-assistant-client";

// Contrato fixo: frontend/src/components/AiAssistantPanel.tsx (ainda não
// implementado — fase RED do TDD). Este import falhará até o componente
// existir, assim como o import de tipos acima falhará até
// frontend/src/lib/ai-assistant-client.ts existir.
import AiAssistantPanel from "@/components/AiAssistantPanel";

/**
 * Contrato de UI assumido para o frontend-builder implementar (SPEC-003 não
 * define textos/rótulos, apenas o contrato de API — fixamos aqui para os
 * testes servirem de especificação executável):
 *
 * - Campo "Tópico" (textarea ou input, obrigatório).
 * - Select "Tom" com as opções value="formal"|"casual"|"tecnico".
 * - Campo "Palavras-chave (separadas por vírgula)" (texto livre, opcional).
 * - Select "Tamanho" com as opções value="short"|"medium"|"long".
 * - Botão "Gerar rascunho" (submit).
 * - Indicador de carregamento com texto contendo "Gerando" enquanto
 *   status === "pending".
 * - Resultado (status "done") exibe título, meta description, tags e um
 *   preview do conteúdo como texto visível na tela.
 * - Botão "Usar este rascunho" que dispara `onDraftReady(result)`.
 * - Erros (status "failed" do job, ou 429 no submit) são exibidos via
 *   `role="alert"`.
 *
 * A spec (SPEC-003) não define o intervalo exato de polling do
 * GET /api/posts/generate-draft/{job_id} — assumimos aqui 2000ms. Os testes
 * que cruzam esse intervalo avançam múltiplos ciclos de `ASSUMED_POLL_INTERVAL_MS`
 * (via fake timers) e mantêm a última resposta mockada estável, para tolerar
 * tanto uma implementação que faz o 1º poll imediatamente quanto uma que só
 * consulta o status após o primeiro intervalo decorrido.
 */
const ASSUMED_POLL_INTERVAL_MS = 2000;

// Título deliberadamente distinto de qualquer texto de tópico usado nos
// testes abaixo (ex.: "Como aplicar SDD no seu time", usado como tópico
// padrão em `reachDoneState`) — um valor igual faria `getByText(title)`
// casar com o próprio `<textarea>` do tópico (que também renderiza seu
// value como texto), mascarando um falso positivo antes do polling
// realmente terminar.
const draftResult: AssistantDraftResult = {
  title: "5 passos para adotar Spec-Driven Development no seu time",
  content_markdown:
    "Este e o conteudo gerado pela IA sobre SDD, cobrindo os principais passos.",
  meta_description: "Guia pratico de Spec-Driven Development para times ageis.",
  tags: ["sdd", "processos", "qualidade"],
};

function mockGenerateDraft(jobId: string, onBody?: (body: Record<string, unknown>) => void) {
  server.use(
    http.post(`${API_URL}/api/posts/generate-draft`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      onBody?.(body);
      return HttpResponse.json({ job_id: jobId, status: "pending" }, { status: 202 });
    })
  );
}

// A N-ésima chamada de GET recebe `responses[N]`; chamadas excedentes
// recebem sempre a última entrada (estado estável), tolerando implementações
// com diferentes números de polls antes do status final.
function mockJobStatusSequence(jobId: string, responses: Array<Record<string, unknown>>) {
  let call = 0;
  server.use(
    http.get(`${API_URL}/api/posts/generate-draft/${jobId}`, () => {
      const response = responses[Math.min(call, responses.length - 1)];
      call += 1;
      return HttpResponse.json(response, { status: 200 });
    })
  );
}

interface FillFields {
  topic?: string;
  tone?: "formal" | "casual" | "tecnico";
  keywords?: string;
  length?: "short" | "medium" | "long";
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, fields: FillFields = {}) {
  if (fields.topic !== undefined) {
    await user.type(screen.getByLabelText(/tópico/i), fields.topic);
  }
  if (fields.tone !== undefined) {
    await user.selectOptions(screen.getByRole("combobox", { name: /tom/i }), fields.tone);
  }
  if (fields.keywords !== undefined) {
    await user.type(screen.getByLabelText(/palavras-chave/i), fields.keywords);
  }
  if (fields.length !== undefined) {
    await user.selectOptions(screen.getByRole("combobox", { name: /tamanho/i }), fields.length);
  }
  await user.click(screen.getByRole("button", { name: /gerar rascunho/i }));
}

// Preenche o tópico, submete, aguarda o estado "Gerando..." e então aguarda
// o resultado aparecer na tela.
//
// Usa espera real (via o timeout estendido de `findByText`) em vez de fake
// timers: o `setInterval` de polling só é criado pelo componente DEPOIS do
// `await screen.findByText(/gerando/i)` resolver — ou seja, ele nasce como um
// timer real. `vi.useFakeTimers()` só passa a interceptar timers criados
// depois de ser chamado; um `setInterval` real já agendado não é afetado por
// `vi.advanceTimersByTimeAsync(...)` (comportamento documentado do fake
// timers do Vitest). Por isso a tentativa original de "avançar" esse
// intervalo com fake timers nunca disparava o segundo poll (o que traz
// `status: "done"`) — daí a espera real abaixo.
async function reachDoneState(
  user: ReturnType<typeof userEvent.setup>,
  jobId: string,
  topic = "Como aplicar SDD no seu time"
) {
  mockGenerateDraft(jobId);
  mockJobStatusSequence(jobId, [
    { job_id: jobId, status: "pending" },
    { job_id: jobId, status: "done", result: draftResult },
  ]);

  await fillAndSubmit(user, { topic });
  await screen.findByText(/gerando/i, {}, { timeout: 3000 });

  await screen.findByText(draftResult.title, {}, { timeout: ASSUMED_POLL_INTERVAL_MS * 2 + 1000 });
}

describe("AiAssistantPanel (SPEC-003)", () => {
  describe("formulário (RF01)", () => {
    it("renderiza tópico (obrigatório), tom, palavras-chave (opcional), tamanho e o botão Gerar rascunho", () => {
      render(<AiAssistantPanel />);

      const topicField = screen.getByLabelText(/tópico/i);
      expect(topicField).toBeInTheDocument();
      expect(topicField).toBeRequired();

      expect(screen.getByRole("combobox", { name: /tom/i })).toBeInTheDocument();

      const keywordsField = screen.getByLabelText(/palavras-chave/i);
      expect(keywordsField).toBeInTheDocument();
      expect(keywordsField).not.toBeRequired();

      expect(screen.getByRole("combobox", { name: /tamanho/i })).toBeInTheDocument();

      expect(screen.getByRole("button", { name: /gerar rascunho/i })).toBeInTheDocument();
    });

    it("dado o tópico vazio (campo obrigatório), quando tenta gerar, então a validação HTML5 required impede o submit e a API não é chamada", async () => {
      const generateSpy = vi.fn();
      server.use(
        http.post(`${API_URL}/api/posts/generate-draft`, () => {
          generateSpy();
          return HttpResponse.json({ job_id: "job-nao-deveria-existir", status: "pending" }, { status: 202 });
        })
      );

      const user = userEvent.setup();
      render(<AiAssistantPanel />);

      // Não preenche o tópico — apenas clica em Gerar rascunho.
      await user.click(screen.getByRole("button", { name: /gerar rascunho/i }));

      expect(generateSpy).not.toHaveBeenCalled();
      expect(screen.queryByText(/gerando/i)).not.toBeInTheDocument();
    });
  });

  it("dado um tópico válido, quando o editor solicita geração, então chama POST /api/posts/generate-draft com os parâmetros informados e entra em estado 'Gerando...' sem esperar a LLM responder (critério de aceite 1)", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    mockGenerateDraft("job-1", (body) => {
      capturedBody = body;
    });
    mockJobStatusSequence("job-1", [{ job_id: "job-1", status: "pending" }]);

    const user = userEvent.setup();
    render(<AiAssistantPanel />);

    await fillAndSubmit(user, {
      topic: "Como usar SDD em times pequenos",
      tone: "casual",
      keywords: "sdd, testes",
      length: "short",
    });

    // O componente não bloqueia esperando a LLM: assim que o 202 com job_id
    // chega, já entra em modo de polling exibindo o indicador de carregamento.
    expect(await screen.findByText(/gerando/i, {}, { timeout: 3000 })).toBeInTheDocument();

    expect(capturedBody).toMatchObject({
      topic: "Como usar SDD em times pequenos",
      tone: "casual",
      keywords: ["sdd", "testes"],
      length: "short",
    });
  });

  it("dado um job concluído com sucesso (status done após polling), quando o editor consulta o status, então exibe título, meta description, tags e preview do conteúdo do rascunho (critério de aceite 2)", async () => {
    const user = userEvent.setup();
    render(<AiAssistantPanel />);

    await reachDoneState(user, "job-2");

    expect(screen.getByText(draftResult.title)).toBeInTheDocument();
    expect(screen.getByText(draftResult.meta_description)).toBeInTheDocument();
    for (const tag of draftResult.tags) {
      expect(screen.getByText(tag)).toBeInTheDocument();
    }
    expect(
      screen.getByText(new RegExp(draftResult.content_markdown.slice(0, 25), "i"))
    ).toBeInTheDocument();
  });

  it("dado o rascunho pronto, quando o editor clica em 'Usar este rascunho', então dispara onDraftReady com o resultado completo", async () => {
    const onDraftReady = vi.fn();
    const user = userEvent.setup();
    render(<AiAssistantPanel onDraftReady={onDraftReady} />);

    await reachDoneState(user, "job-3");

    await user.click(screen.getByRole("button", { name: /usar este rascunho/i }));

    expect(onDraftReady).toHaveBeenCalledTimes(1);
    expect(onDraftReady).toHaveBeenCalledWith(draftResult);
  });

  it("dado que a API da LLM falha (job retorna status failed), quando o editor consulta o status, então exibe a mensagem de erro via role=alert sem quebrar a UI (critério de aceite 3)", async () => {
    const errorMessage = "Não foi possível gerar o rascunho. Tente novamente mais tarde.";
    mockGenerateDraft("job-4");
    mockJobStatusSequence("job-4", [{ job_id: "job-4", status: "failed", error: errorMessage }]);

    const user = userEvent.setup();
    render(<AiAssistantPanel />);

    await fillAndSubmit(user, { topic: "Tópico cuja geração falha na LLM" });
    await screen.findByText(/gerando/i, {}, { timeout: 3000 });

    expect(
      await screen.findByRole("alert", {}, { timeout: ASSUMED_POLL_INTERVAL_MS * 2 + 1000 })
    ).toHaveTextContent(/não foi possível gerar o rascunho/i);
    // A UI continua íntegra: o formulário/botão de gerar continuam disponíveis
    // para uma nova tentativa.
    expect(screen.getByRole("button", { name: /gerar rascunho/i })).toBeInTheDocument();
  });

  it("dado um usuário que excedeu o rate limit, quando solicita nova geração, então POST retorna 429 e exibe a mensagem de limite excedido via role=alert (critério de aceite 4)", async () => {
    server.use(
      http.post(`${API_URL}/api/posts/generate-draft`, () =>
        HttpResponse.json({ detail: "Rate limit exceeded" }, { status: 429 })
      )
    );

    const user = userEvent.setup();
    render(<AiAssistantPanel />);

    await fillAndSubmit(user, { topic: "Mais um tópico para gerar" });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /limite de gerações excedido, tente novamente mais tarde\./i
    );
    expect(screen.queryByText(/gerando/i)).not.toBeInTheDocument();
  });
});
