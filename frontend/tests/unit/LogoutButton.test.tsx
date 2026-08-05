import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Contrato fixo: frontend/src/components/LogoutButton.tsx
import LogoutButton from "@/components/LogoutButton";

describe("LogoutButton (SPEC-001)", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("renderiza um botão com nome acessível 'Sair'", () => {
    render(<LogoutButton />);

    expect(screen.getByRole("button", { name: /sair/i })).toBeInTheDocument();
  });

  it("dado um usuário autenticado, quando faz logout, chama POST /api/auth/logout e redireciona para /login (critério de aceite 5, RF06)", async () => {
    let logoutCalled = false;
    server.use(
      http.post(`${API_URL}/api/auth/logout`, () => {
        logoutCalled = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    const user = userEvent.setup();
    render(<LogoutButton />);

    await user.click(screen.getByRole("button", { name: /sair/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/login"));
    expect(logoutCalled).toBe(true);
  });
});
