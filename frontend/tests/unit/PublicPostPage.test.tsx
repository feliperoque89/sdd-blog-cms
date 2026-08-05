import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { PublicPost } from "@/lib/posts-client";

// notFound() do next/navigation lança um erro especial
// (NEXT_HTTP_ERROR_FALLBACK;404 no Next.js real) que interrompe a
// renderização. Reproduzimos esse comportamento com um erro sentinela, no
// mesmo espírito do mock de redirect() em AdminLayout.test.tsx, para que o
// teste funcione independentemente de a implementação ter um `return`
// explícito após a chamada (no Next.js real isso é desnecessário).
const { notFoundMock } = vi.hoisted(() => ({
  notFoundMock: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}));

// PostPage é um Server Component assíncrono (params: Promise<{ slug:
// string }>) — mesmo padrão de invocação direta usado em
// AdminLayout.test.tsx e PublicPostsPage.test.tsx.
//
// Contrato fixo: frontend/src/app/(public)/posts/[slug]/page.tsx
import PostPage from "@/app/(public)/posts/[slug]/page";

describe("PostPage — post individual do blog público (SPEC-002)", () => {
  beforeEach(() => {
    notFoundMock.mockClear();
  });

  it("dado um slug inexistente/draft (GET /api/posts/{slug} -> 404), então chama notFound() (RF07, critério de aceite 3)", async () => {
    server.use(
      http.get(`${API_URL}/api/posts/:slug`, () =>
        HttpResponse.json({ detail: "Não encontrado." }, { status: 404 })
      )
    );

    await expect(
      PostPage({ params: Promise.resolve({ slug: "inexistente" }) })
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
  });

  it("dado um post publicado existente (GET /api/posts/{slug} -> 200), então renderiza título e conteúdo do post (RF07)", async () => {
    const post: PublicPost = {
      id: "post-1",
      title: "Como usar SDD",
      slug: "como-usar-sdd",
      content_markdown: "Conteúdo completo do post em markdown.",
      category_id: "tecnologia",
      tags: ["sdd"],
      cover_image_url: null,
      published_at: "2026-01-01T00:00:00Z",
    };

    let capturedSlug: string | null = null;
    server.use(
      http.get(`${API_URL}/api/posts/:slug`, ({ params }) => {
        capturedSlug = String(params.slug);
        return HttpResponse.json(post, { status: 200 });
      })
    );

    const element = await PostPage({ params: Promise.resolve({ slug: "como-usar-sdd" }) });
    render(element as React.ReactElement);

    expect(capturedSlug).toBe("como-usar-sdd");
    expect(screen.getByText(post.title)).toBeInTheDocument();
    expect(screen.getByText(/conteúdo completo do post em markdown/i)).toBeInTheDocument();
    expect(notFoundMock).not.toHaveBeenCalled();
  });
});
