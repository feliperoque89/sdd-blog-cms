import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL, mockUser } from "../mocks/handlers";

// LoginForm é Client Component (usa useRouter para navegação pós-login),
// então next/navigation precisa ser mockado. vi.hoisted garante que
// `pushMock` exista antes de vi.mock ser içado para o topo do módulo.
const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Import depois do vi.mock — contrato fixo: frontend/src/components/LoginForm.tsx
import LoginForm from "@/components/LoginForm";

async function fillAndSubmit(
  user: ReturnType<typeof userEvent.setup>,
  { email, password }: { email?: string; password?: string }
) {
  if (email !== undefined) {
    await user.type(screen.getByLabelText(/e-mail/i), email);
  }
  if (password !== undefined) {
    await user.type(screen.getByLabelText(/senha/i), password);
  }
  await user.click(screen.getByRole("button", { name: /entrar/i }));
}

describe("LoginForm (SPEC-001)", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("renderiza os campos E-mail e Senha e o botão Entrar (RF01)", () => {
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/e-mail/i);
    const passwordInput = screen.getByLabelText(/senha/i);

    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute("type", "email");
    expect(emailInput).toBeRequired();

    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(passwordInput).toBeRequired();

    expect(screen.getByRole("button", { name: /entrar/i })).toBeInTheDocument();
  });

  it("dado e-mail e senha corretos, quando o usuário faz login, então é redirecionado para /admin (critério de aceite 1)", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user, { email: "editor@exemplo.com", password: "senha-correta" });

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/admin"));
  });

  it("dado credenciais inválidas, quando tenta logar, então recebe 401, exibe erro e não redireciona (critério de aceite 2)", async () => {
    server.use(
      http.post(`${API_URL}/api/auth/login`, () =>
        HttpResponse.json({ detail: "E-mail ou senha inválidos." }, { status: 401 })
      )
    );

    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user, { email: "editor@exemplo.com", password: "senha-errada" });

    expect(await screen.findByText(/e-mail ou senha inválidos/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("dado rate limit excedido (429), quando tenta logar, então exibe mensagem de muitas tentativas e não redireciona (RNF02)", async () => {
    server.use(
      http.post(`${API_URL}/api/auth/login`, () =>
        HttpResponse.json(
          { detail: "Muitas tentativas de login. Tente novamente em instantes." },
          { status: 429 }
        )
      )
    );

    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user, { email: "editor@exemplo.com", password: "qualquer-coisa" });

    expect(await screen.findByText(/muitas tentativas/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("desabilita o botão Entrar enquanto o login está em andamento, evitando duplo submit", async () => {
    // Handler que só resolve quando `resolveLogin` é chamado manualmente,
    // simulando uma requisição em voo para inspecionar o estado intermediário
    // (botão desabilitado) antes da resposta chegar.
    let resolveLogin: () => void = () => {};
    const pending = new Promise<void>((resolve) => {
      resolveLogin = resolve;
    });

    server.use(
      http.post(`${API_URL}/api/auth/login`, async () => {
        await pending;
        return HttpResponse.json(mockUser, { status: 200 });
      })
    );

    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/e-mail/i), "editor@exemplo.com");
    await user.type(screen.getByLabelText(/senha/i), "senha-correta");

    const submitButton = screen.getByRole("button", { name: /entrar/i });
    await user.click(submitButton);

    await waitFor(() => expect(submitButton).toBeDisabled());

    resolveLogin();

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/admin"));
  });

  it("não envia requisição de login quando o e-mail está vazio (validação HTML5 required)", async () => {
    const loginSpy = vi.fn();
    server.use(
      http.post(`${API_URL}/api/auth/login`, () => {
        loginSpy();
        return HttpResponse.json(mockUser, { status: 200 });
      })
    );

    const user = userEvent.setup();
    render(<LoginForm />);

    // Preenche apenas a senha, deixando o e-mail (required) vazio.
    await fillAndSubmit(user, { password: "senha-correta" });

    expect(loginSpy).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("não envia requisição de login quando a senha está vazia (validação HTML5 required)", async () => {
    const loginSpy = vi.fn();
    server.use(
      http.post(`${API_URL}/api/auth/login`, () => {
        loginSpy();
        return HttpResponse.json(mockUser, { status: 200 });
      })
    );

    const user = userEvent.setup();
    render(<LoginForm />);

    // Preenche apenas o e-mail, deixando a senha (required) vazia.
    await fillAndSubmit(user, { email: "editor@exemplo.com" });

    expect(loginSpy).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });
});

// Critério de aceite 4 (papel `editor` tentando rota admin-only -> 403) não é
// testado aqui: SPEC-001 não define quais rotas do frontend são admin-only
// vs. editor-accessible (ver seção "Fora de escopo" da spec — isso é
// deferido a specs futuras). O comportamento de 401/403 vindo da API já é
// coberto nos testes de LoginForm (401) e no proxy/AdminLayout (401 -> /login).
