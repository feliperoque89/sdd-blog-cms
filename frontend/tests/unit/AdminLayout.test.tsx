import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL, mockUser } from "../mocks/handlers";

// AdminLayout é um Server Component assíncrono que verifica a sessão via
// GET /api/auth/me e usa redirect() do next/navigation quando não há
// sessão válida (critério de aceite 3: "token expirado ao acessar rota
// protegida -> 401"). O proxy.ts só faz checagem otimista de presença de
// cookie (ver proxy.test.ts); quem efetivamente valida a sessão contra o
// backend é este layout.
//
// O redirect() real do Next.js interrompe a renderização lançando um erro
// especial (NEXT_REDIRECT). Reproduzimos esse comportamento no mock para que
// o teste funcione independentemente de a implementação ter um `return`
// explícito após a chamada de redirect() (no Next.js real isso é
// desnecessário, pois redirect() nunca retorna).
const { redirectMock } = vi.hoisted(() => ({
  redirectMock: vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT:${url}`);
  }),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

// Alguns caminhos de implementação podem usar next/headers `cookies()` para
// repassar o cookie de sessão na chamada a /api/auth/me. Como isso exige um
// contexto de requisição que não existe fora do runtime do Next.js, damos um
// stub inofensivo aqui — o teste não depende de cookies reais serem
// repassados, apenas do status HTTP retornado por /api/auth/me (mockado via
// MSW).
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    toString: (): string => "",
    get: (): undefined => undefined,
    getAll: (): unknown[] => [],
  })),
}));

// Contrato fixo: frontend/src/app/(admin)/layout.tsx
import AdminLayout from "@/app/(admin)/layout";

describe("AdminLayout (SPEC-001)", () => {
  beforeEach(() => {
    redirectMock.mockClear();
  });

  it("dado um token expirado/ausente, quando acessa uma rota /admin/*, então GET /api/auth/me retorna 401 e o layout redireciona para /login (critério de aceite 3)", async () => {
    server.use(
      http.get(`${API_URL}/api/auth/me`, () =>
        HttpResponse.json({ detail: "Não autenticado." }, { status: 401 })
      )
    );

    await expect(
      AdminLayout({ children: <div>Painel Admin</div> as ReactNode })
    ).rejects.toThrow("NEXT_REDIRECT:/login");

    expect(redirectMock).toHaveBeenCalledWith("/login");
  });

  it("dado um usuário autenticado (GET /api/auth/me -> 200), quando acessa uma rota /admin/*, então renderiza o conteúdo sem redirecionar", async () => {
    server.use(
      http.get(`${API_URL}/api/auth/me`, () => HttpResponse.json(mockUser, { status: 200 }))
    );

    const element = await AdminLayout({ children: <div>Painel Admin</div> as ReactNode });
    render(element as React.ReactElement);

    expect(screen.getByText("Painel Admin")).toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
  });
});

// Critério de aceite 4 (papel `editor` tentando rota admin-only -> 403) não é
// testado aqui: SPEC-001 não define quais rotas do frontend são admin-only
// vs. editor-accessible (ver "Fora de escopo" da spec) — deferido a specs
// futuras. Este layout só verifica autenticação (usuário existe/sessão
// válida), não autorização por papel.
