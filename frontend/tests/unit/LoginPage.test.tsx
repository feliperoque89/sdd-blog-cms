import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// A página apenas renderiza <LoginForm />, que é Client Component e usa
// useRouter — precisa do mesmo mock de next/navigation usado em
// LoginForm.test.tsx para poder ser montada em jsdom.
const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Contrato fixo: frontend/src/app/(public)/login/page.tsx
import LoginPage from "@/app/(public)/login/page";

describe("LoginPage (SPEC-001)", () => {
  it("renderiza o LoginForm com os campos E-mail, Senha e o botão Entrar", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/senha/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /entrar/i })).toBeInTheDocument();
  });
});
