import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/**
 * Servidor MSW compartilhado por toda a suíte (backend real nunca é chamado
 * em teste unitário — ver specs/TESTING.md). Ciclo de vida (listen/reset/close)
 * é controlado globalmente em `vitest.setup.ts`.
 */
export const server = setupServer(...handlers);
