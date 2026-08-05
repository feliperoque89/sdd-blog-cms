import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./tests/mocks/server";

// Default de teste para NEXT_PUBLIC_API_URL, espelhando frontend/.env.example.
// Não sobrescreve se algo já tiver definido a variável (ex: CI).
process.env.NEXT_PUBLIC_API_URL ??= "http://localhost:8000";

// MSW intercepta toda chamada de rede nos testes unitários — nunca falamos
// com o backend real (ver specs/TESTING.md). Qualquer requisição não coberta
// por um handler falha o teste (onUnhandledRequest: "error") para evitar
// chamadas de rede silenciosas para fora do ambiente de teste.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
