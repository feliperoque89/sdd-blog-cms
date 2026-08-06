import { http, HttpResponse } from "msw";

/**
 * Base URL do backend, espelhando `NEXT_PUBLIC_API_URL` (ver frontend/.env.example).
 * Mantemos um fallback explícito para o mesmo default usado pela aplicação,
 * garantindo que os handlers do MSW interceptem as mesmas URLs que o código
 * de produção efetivamente chama.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const mockUser = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Ana Editor",
  role: "editor" as const,
};

/**
 * Categorias mockadas para o seletor do `PostEditor` (SPEC-002 / RF01).
 * IDs escolhidos para casar com os `category_id` já usados como fixture em
 * `PostEditor.test.tsx`/`AdminPostsPage.test.tsx` (`"tecnologia"`,
 * `"cultura"`), evitando reescrever esses testes por completo.
 */
export const mockCategories = [
  { id: "tecnologia", name: "Tecnologia" },
  { id: "cultura", name: "Cultura" },
];

/**
 * Handlers "felizes" usados como padrão em todos os testes (SPEC-001/002).
 * Cada teste que precisa de um cenário de erro sobrescreve o handler
 * relevante via `server.use(...)`.
 */
export const handlers = [
  http.post(`${API_URL}/api/auth/login`, async () => {
    return HttpResponse.json(mockUser, { status: 200 });
  }),

  http.post(`${API_URL}/api/auth/logout`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API_URL}/api/auth/me`, () => {
    return HttpResponse.json(mockUser, { status: 200 });
  }),

  http.get(`${API_URL}/api/admin/categories`, () => {
    return HttpResponse.json(mockCategories, { status: 200 });
  }),
];
