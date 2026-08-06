import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { AiSettingsPublic } from "@/lib/ai-settings-client";

// Contrato fixo: frontend/src/app/(admin)/admin/ai-settings/page.tsx (SPEC-004)
import AiSettingsPage from "@/app/(admin)/admin/ai-settings/page";

function mockGetAiSettings(overrides: Partial<AiSettingsPublic> = {}) {
  const body: AiSettingsPublic = {
    provider: "anthropic",
    model: "claude-sonnet-4-6",
    base_url: "https://api.anthropic.com/v1/messages",
    api_key_last4: null,
    api_key_set: false,
    max_output_tokens: 4096,
    timeout_seconds: 30,
    ...overrides,
  };
  server.use(
    http.get(`${API_URL}/api/admin/ai-settings`, () => HttpResponse.json(body, { status: 200 }))
  );
  return body;
}

describe("AiSettingsPage (SPEC-004)", () => {
  it("ao montar, busca GET /api/admin/ai-settings e preenche o formulário com os valores atuais", async () => {
    mockGetAiSettings({
      provider: "gemini",
      model: "claude-opus-5",
      base_url: "https://api.anthropic.com/v1/messages",
      api_key_set: true,
      api_key_last4: "9999",
      max_output_tokens: 2048,
      timeout_seconds: 25,
    });

    render(<AiSettingsPage />);

    expect(await screen.findByLabelText(/provider/i)).toHaveValue("gemini");
    expect(screen.getByLabelText(/model/i)).toHaveValue("claude-opus-5");
    expect(screen.getByLabelText(/base url/i)).toHaveValue(
      "https://api.anthropic.com/v1/messages"
    );
    expect(screen.getByLabelText(/máximo de tokens de saída/i)).toHaveValue(2048);
    expect(screen.getByLabelText(/timeout/i)).toHaveValue(25);
    // A API key nunca vem em texto puro — o campo começa vazio, só o rótulo
    // indica que já existe uma configurada (últimos 4 dígitos).
    expect(screen.getByLabelText(/api key/i)).toHaveValue("");
    expect(screen.getByText(/9999/)).toBeInTheDocument();
  });

  it("dado o provider alterado para gemini, quando salva, então envia provider: 'gemini' no PUT", async () => {
    mockGetAiSettings();
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_URL}/api/admin/ai-settings`, async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            provider: capturedBody.provider,
            model: capturedBody.model,
            base_url: capturedBody.base_url,
            api_key_last4: null,
            api_key_set: false,
            max_output_tokens: capturedBody.max_output_tokens,
            timeout_seconds: capturedBody.timeout_seconds,
          },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AiSettingsPage />);

    await screen.findByLabelText(/model/i);
    await user.selectOptions(screen.getByLabelText(/provider/i), "gemini");
    expect(screen.getByLabelText(/base url/i)).toHaveValue(
      "https://generativelanguage.googleapis.com/v1beta/models"
    );
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).toMatchObject({
      provider: "gemini",
      base_url: "https://generativelanguage.googleapis.com/v1beta/models",
    });
  });

  it("dado o formulário preenchido, quando salva, então chama PUT /api/admin/ai-settings com os campos informados", async () => {
    mockGetAiSettings();
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_URL}/api/admin/ai-settings`, async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            provider: capturedBody.provider,
            model: capturedBody.model,
            base_url: capturedBody.base_url,
            api_key_last4: "abcd",
            api_key_set: true,
            max_output_tokens: capturedBody.max_output_tokens,
            timeout_seconds: capturedBody.timeout_seconds,
          },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AiSettingsPage />);

    const modelInput = await screen.findByLabelText(/model/i);
    await user.clear(modelInput);
    await user.type(modelInput, "claude-sonnet-5");
    await user.type(screen.getByLabelText(/api key/i), "sk-ant-abcd");
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).toMatchObject({
      model: "claude-sonnet-5",
      api_key: "sk-ant-abcd",
    });
    expect(await screen.findByText(/configuração salva com sucesso/i)).toBeInTheDocument();
  });

  it("dado o campo de api key em branco, quando salva, então não envia api_key (preserva a chave já salva)", async () => {
    mockGetAiSettings({ api_key_set: true, api_key_last4: "1234" });
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_URL}/api/admin/ai-settings`, async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            provider: capturedBody.provider,
            model: capturedBody.model,
            base_url: capturedBody.base_url,
            api_key_last4: "1234",
            api_key_set: true,
            max_output_tokens: null,
            timeout_seconds: null,
          },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AiSettingsPage />);

    await screen.findByLabelText(/model/i);
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).not.toHaveProperty("api_key");
  });

  it("dado um erro da API ao salvar, exibe a mensagem via role=alert sem quebrar a UI", async () => {
    mockGetAiSettings();
    server.use(
      http.put(`${API_URL}/api/admin/ai-settings`, () =>
        HttpResponse.json({ detail: "Model é obrigatório." }, { status: 422 })
      )
    );

    const user = userEvent.setup();
    render(<AiSettingsPage />);

    await screen.findByLabelText(/model/i);
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/model é obrigatório/i);
    expect(screen.getByRole("button", { name: /salvar/i })).toBeInTheDocument();
  });
});
