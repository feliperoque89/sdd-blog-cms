import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { PublicPost } from "@/lib/posts-client";

// HomePage é um Server Component assíncrono (searchParams: Promise<{ page?:
// string }>). Seguindo o padrão de AdminLayout.test.tsx, chamamos a função da
// página diretamente (await) para obter o elemento já resolvido e só então
// usamos render() — Vitest/RTL não sabe renderizar Server Components async
// via JSX diretamente.
//
// Contrato fixo: frontend/src/app/(public)/page.tsx
import HomePage from "@/app/(public)/page";

const postA: PublicPost = {
  id: "post-a",
  title: "Post A",
  slug: "post-a",
  content_markdown: "Conteúdo do post A.",
  category_id: "tecnologia",
  tags: ["sdd"],
  cover_image_url: null,
  published_at: "2026-01-02T00:00:00Z",
};

const postB: PublicPost = {
  id: "post-b",
  title: "Post B",
  slug: "post-b",
  content_markdown: "Conteúdo do post B.",
  category_id: "cultura",
  tags: [],
  cover_image_url: null,
  published_at: "2026-01-01T00:00:00Z",
};

describe("HomePage — blog público (SPEC-002)", () => {
  it("dado GET /api/posts retornando itens paginados, então renderiza o título de cada post e um link para /posts/{slug} (RF06, critério de aceite 5)", async () => {
    server.use(
      http.get(`${API_URL}/api/posts`, () =>
        HttpResponse.json(
          { items: [postA, postB], total: 2, page: 1, page_size: 10 },
          { status: 200 }
        )
      )
    );

    const element = await HomePage({ searchParams: Promise.resolve({}) });
    render(element as React.ReactElement);

    expect(screen.getByText(postA.title)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(postA.title, "i") })).toHaveAttribute(
      "href",
      `/posts/${postA.slug}`
    );

    expect(screen.getByText(postB.title)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(postB.title, "i") })).toHaveAttribute(
      "href",
      `/posts/${postB.slug}`
    );
  });

  it("dado searchParams com page='2', então propaga ?page=2 na chamada a GET /api/posts (RNF02)", async () => {
    let capturedPage: string | null = null;
    server.use(
      http.get(`${API_URL}/api/posts`, ({ request }) => {
        const url = new URL(request.url);
        capturedPage = url.searchParams.get("page");
        return HttpResponse.json(
          { items: [], total: 0, page: Number(capturedPage ?? "1"), page_size: 10 },
          { status: 200 }
        );
      })
    );

    const element = await HomePage({ searchParams: Promise.resolve({ page: "2" }) });
    render(element as React.ReactElement);

    expect(capturedPage).toBe("2");
  });
});
