import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { AdminPost } from "@/lib/posts-client";

// Contrato fixo: frontend/src/app/(admin)/admin/posts/page.tsx — página
// inteira gerencia estado (lista, filtros, paginação, editor inline,
// exclusão) do lado do cliente, por isso é renderizada diretamente sem
// props, no mesmo espírito de LoginPage.test.tsx.
import AdminPostsPage from "@/app/(admin)/admin/posts/page";

const draftPost: AdminPost = {
  id: "post-draft",
  title: "Rascunho em andamento",
  slug: "rascunho-em-andamento",
  content_markdown: "Conteúdo do rascunho.",
  category_id: "tecnologia",
  tags: ["sdd"],
  cover_image_url: null,
  status: "draft",
  published_at: null,
  created_at: "2026-01-01T00:00:00Z",
  deleted_at: null,
};

const publishedPost: AdminPost = {
  id: "post-published",
  title: "Post já publicado",
  slug: "post-ja-publicado",
  content_markdown: "Conteúdo publicado.",
  category_id: "cultura",
  tags: ["blog"],
  cover_image_url: null,
  status: "published",
  published_at: "2026-01-02T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  deleted_at: null,
};

function mockAdminPostsList(items: AdminPost[]) {
  server.use(
    http.get(`${API_URL}/api/admin/posts`, () =>
      HttpResponse.json({ items, total: items.length, page: 1, page_size: 10 }, { status: 200 })
    )
  );
}

// Assume que cada post é renderizado como uma "linha" (role="row", ex.: uma
// <table>/<tr> ou qualquer elemento com role="row") contendo título, status
// e os botões de ação — terminologia usada explicitamente na spec desta
// tarefa ("Botão 'Editar' em uma linha").
function findRowByText(text: string) {
  const rows = screen.getAllByRole("row");
  const row = rows.find((candidate) => within(candidate).queryByText(text));
  if (!row) {
    throw new Error(`Nenhuma linha encontrada contendo o texto: ${text}`);
  }
  return row;
}

describe("AdminPostsPage (SPEC-002)", () => {
  beforeEach(() => {
    // Alguns fluxos de exclusão podem usar window.confirm antes de chamar a
    // API — garantimos que, se existir, sempre confirme, para o teste focar
    // no critério de aceite (remoção da lista), não na caixa de diálogo.
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("ao montar, busca e lista posts de GET /api/admin/posts, mostrando título e status de cada um (RF05)", async () => {
    mockAdminPostsList([draftPost, publishedPost]);

    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);
    expect(screen.getByText(publishedPost.title)).toBeInTheDocument();

    const draftRow = findRowByText(draftPost.title);
    expect(within(draftRow).getByText(new RegExp(draftPost.status, "i"))).toBeInTheDocument();

    const publishedRow = findRowByText(publishedPost.title);
    expect(
      within(publishedRow).getByText(new RegExp(publishedPost.status, "i"))
    ).toBeInTheDocument();
  });

  it("dado o filtro de status, quando seleciona 'draft', então refaz o fetch com ?status=draft e some com os posts publicados (RF05)", async () => {
    let lastStatus: string | null = null;
    server.use(
      http.get(`${API_URL}/api/admin/posts`, ({ request }) => {
        const url = new URL(request.url);
        lastStatus = url.searchParams.get("status");
        const items =
          lastStatus === "draft"
            ? [draftPost]
            : lastStatus === "published"
              ? [publishedPost]
              : [draftPost, publishedPost];
        return HttpResponse.json(
          { items, total: items.length, page: 1, page_size: 10 },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);
    expect(screen.getByText(publishedPost.title)).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: /status/i }), "draft");

    await waitFor(() => expect(lastStatus).toBe("draft"));
    await waitFor(() => expect(screen.queryByText(publishedPost.title)).not.toBeInTheDocument());
    expect(screen.getByText(draftPost.title)).toBeInTheDocument();
  });

  it("dado o botão 'Novo post', quando clicado, revela o PostEditor em modo create; após sucesso, o novo post aparece na lista", async () => {
    mockAdminPostsList([draftPost]);

    const newPost: AdminPost = {
      id: "post-novo",
      title: "Post recém-criado",
      slug: "post-recem-criado",
      content_markdown: "Conteúdo novo.",
      category_id: "tecnologia",
      tags: [],
      cover_image_url: null,
      status: "draft",
      published_at: null,
      created_at: "2026-01-03T00:00:00Z",
      deleted_at: null,
    };
    server.use(
      http.post(`${API_URL}/api/admin/posts`, () => HttpResponse.json(newPost, { status: 201 }))
    );

    const user = userEvent.setup();
    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);

    await user.click(screen.getByRole("button", { name: /novo post/i }));

    // O formulário de criação (PostEditor) fica visível.
    const titleInput = await screen.findByLabelText(/título/i);
    await user.type(titleInput, newPost.title);
    await user.type(screen.getByLabelText(/conteúdo/i), newPost.content_markdown);
    await screen.findByRole("option", { name: /tecnologia/i });
    await user.selectOptions(screen.getByLabelText(/categoria/i), newPost.category_id);
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    expect(await screen.findByText(newPost.title)).toBeInTheDocument();
  });

  it("dado o botão 'Editar' em uma linha, quando clicado, revela o PostEditor pré-preenchido com os dados daquela linha, sem nova requisição de leitura", async () => {
    let getCalls = 0;
    server.use(
      http.get(`${API_URL}/api/admin/posts`, () => {
        getCalls += 1;
        return HttpResponse.json(
          { items: [draftPost, publishedPost], total: 2, page: 1, page_size: 10 },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);
    expect(getCalls).toBe(1);

    const row = findRowByText(draftPost.title);
    await user.click(within(row).getByRole("button", { name: /editar/i }));

    expect(screen.getByLabelText(/título/i)).toHaveValue(draftPost.title);
    await waitFor(() =>
      expect(screen.getByLabelText(/categoria/i)).toHaveValue(draftPost.category_id)
    );
    expect(screen.getByLabelText(/conteúdo/i)).toHaveValue(draftPost.content_markdown);

    // Os dados já vieram da listagem — não deve haver nova requisição GET.
    expect(getCalls).toBe(1);
  });

  it("dado o botão 'Excluir' em uma linha, quando clicado, chama DELETE /api/admin/posts/{id} e remove o post da lista exibida (RF04, critério de aceite 4)", async () => {
    mockAdminPostsList([draftPost, publishedPost]);

    let deletedId: string | null = null;
    server.use(
      http.delete(`${API_URL}/api/admin/posts/:id`, ({ params }) => {
        deletedId = String(params.id);
        return new HttpResponse(null, { status: 204 });
      })
    );

    const user = userEvent.setup();
    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);

    const row = findRowByText(draftPost.title);
    await user.click(within(row).getByRole("button", { name: /excluir/i }));

    await waitFor(() => expect(screen.queryByText(draftPost.title)).not.toBeInTheDocument());
    expect(deletedId).toBe(draftPost.id);
    // O post publicado, não excluído, continua na lista.
    expect(screen.getByText(publishedPost.title)).toBeInTheDocument();
  });

  it("dado metadados de paginação {total, page, page_size}, quando avança para a página 2, então refaz o fetch com ?page=2 (RNF02)", async () => {
    let lastPage: string | null = null;
    server.use(
      http.get(`${API_URL}/api/admin/posts`, ({ request }) => {
        const url = new URL(request.url);
        lastPage = url.searchParams.get("page") ?? "1";
        const items = lastPage === "2" ? [publishedPost] : [draftPost];
        return HttpResponse.json(
          { items, total: 2, page: Number(lastPage), page_size: 1 },
          { status: 200 }
        );
      })
    );

    const user = userEvent.setup();
    render(<AdminPostsPage />);

    await screen.findByText(draftPost.title);

    // Assume um botão de avançar página com nome acessível contendo
    // "Próxima" (ex.: "Próxima página").
    await user.click(screen.getByRole("button", { name: /pr[oó]xima/i }));

    await waitFor(() => expect(lastPage).toBe("2"));
    await waitFor(() => expect(screen.getByText(publishedPost.title)).toBeInTheDocument());
  });
});
