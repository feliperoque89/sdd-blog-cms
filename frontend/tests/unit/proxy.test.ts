import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
// Contrato fixo: frontend/proxy.ts (raiz do projeto Next.js 16 — o arquivo
// `middleware.ts` foi renomeado para `proxy.ts` e a função exportada é
// `proxy`, não `middleware`, a partir do Next.js 16; confirmado via
// node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md
// e node_modules/next/package.json (versão instalada: 16.3.0)).
import { proxy } from "../../proxy";

function expectRedirectTo(response: Response, pathname: string) {
  expect(response.status).toBeGreaterThanOrEqual(300);
  expect(response.status).toBeLessThan(400);
  const location = response.headers.get("location");
  expect(location).not.toBeNull();
  expect(new URL(location as string).pathname).toBe(pathname);
}

function expectPassThrough(response: Response) {
  // NextResponse.next() não define header Location e não é um status de
  // redirecionamento (ver spike local: status 200, location: null).
  expect(response.headers.get("location")).toBeNull();
  expect(response.status).toBeLessThan(300);
}

describe("proxy (SPEC-001, RF04)", () => {
  it("redireciona /admin para /login quando não há cookie access_token (critério de aceite 3)", async () => {
    const request = new NextRequest("http://localhost:3000/admin");

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectRedirectTo(response as Response, "/login");
  });

  it("redireciona qualquer subrota /admin/* para /login quando não há cookie access_token", async () => {
    const request = new NextRequest("http://localhost:3000/admin/posts/123");

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectRedirectTo(response as Response, "/login");
  });

  it("permite o acesso a /admin quando o cookie access_token está presente (checagem otimista de presença, não valida o JWT)", async () => {
    const request = new NextRequest("http://localhost:3000/admin", {
      headers: { cookie: "access_token=some-token-value" },
    });

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectPassThrough(response as Response);
  });

  it("permite o acesso a uma subrota /admin/* quando o cookie access_token está presente", async () => {
    const request = new NextRequest("http://localhost:3000/admin/posts/123", {
      headers: { cookie: "access_token=some-token-value" },
    });

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectPassThrough(response as Response);
  });

  it("nunca redireciona /login, mesmo sem cookie access_token", async () => {
    const request = new NextRequest("http://localhost:3000/login");

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectPassThrough(response as Response);
  });

  it("nunca redireciona /login quando há cookie access_token", async () => {
    const request = new NextRequest("http://localhost:3000/login", {
      headers: { cookie: "access_token=some-token-value" },
    });

    const response = await proxy(request);

    expect(response).toBeDefined();
    expectPassThrough(response as Response);
  });

  it("nunca redireciona rotas públicas fora de /admin, independentemente do cookie", async () => {
    const withoutCookie = new NextRequest("http://localhost:3000/");
    const withCookie = new NextRequest("http://localhost:3000/", {
      headers: { cookie: "access_token=some-token-value" },
    });

    const responseWithoutCookie = await proxy(withoutCookie);
    const responseWithCookie = await proxy(withCookie);

    expect(responseWithoutCookie).toBeDefined();
    expect(responseWithCookie).toBeDefined();
    expectPassThrough(responseWithoutCookie as Response);
    expectPassThrough(responseWithCookie as Response);
  });
});

// Critério de aceite 4 (papel `editor` tentando rota admin-only -> 403) não é
// testado aqui: o proxy só faz uma checagem otimista de presença do cookie
// (nunca valida o JWT nem o papel do usuário, já que o segredo de assinatura
// do JWT nunca pode estar disponível no frontend). SPEC-001 também não
// define quais rotas do frontend são admin-only vs. editor-accessible (ver
// "Fora de escopo" da spec) — deferido a specs futuras.
