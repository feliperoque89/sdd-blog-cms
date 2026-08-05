import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_URL } from "../mocks/handlers";
import type { AdminPost } from "@/lib/posts-client";

// Contrato fixo: frontend/src/components/PostEditor.tsx
import PostEditor from "@/components/PostEditor";

function buildAdminPost(overrides: Partial<AdminPost> = {}): AdminPost {
  return {
    id: "post-1",
    title: "Como usar SDD",
    slug: "como-usar-sdd",
    content_markdown: "# Título\n\nConteúdo do post.",
    category_id: "tecnologia",
    tags: ["sdd", "testes"],
    cover_image_url: null,
    status: "draft",
    published_at: null,
    created_at: "2026-01-01T00:00:00Z",
    deleted_at: null,
    ...overrides,
  };
}

interface FillFields {
  title?: string;
  content?: string;
  category?: string;
  tags?: string;
  coverImageUrl?: string;
  status?: "draft" | "published";
}

// Preenche apenas os campos informados, deixando os demais como estão (útil
// para os testes de validação HTML5 `required`, que precisam de um campo
// obrigatório vazio).
async function fillForm(user: ReturnType<typeof userEvent.setup>, fields: FillFields) {
  if (fields.title !== undefined) {
    await user.type(screen.getByLabelText(/título/i), fields.title);
  }
  if (fields.content !== undefined) {
    await user.type(screen.getByLabelText(/conteúdo/i), fields.content);
  }
  if (fields.category !== undefined) {
    await user.type(screen.getByLabelText(/categoria/i), fields.category);
  }
  if (fields.tags !== undefined) {
    await user.type(screen.getByLabelText(/tags/i), fields.tags);
  }
  if (fields.coverImageUrl !== undefined) {
    await user.type(screen.getByLabelText(/imagem de capa/i), fields.coverImageUrl);
  }
  if (fields.status !== undefined) {
    await user.selectOptions(screen.getByRole("combobox", { name: /status/i }), fields.status);
  }
}

describe("PostEditor (SPEC-002)", () => {
  describe("modo create (RF01)", () => {
    it("renderiza título, conteúdo, categoria, tags, imagem de capa e status vazios", () => {
      render(<PostEditor mode="create" />);

      expect(screen.getByLabelText(/título/i)).toHaveValue("");
      expect(screen.getByLabelText(/título/i)).toBeRequired();
      expect(screen.getByLabelText(/conteúdo/i)).toHaveValue("");
      expect(screen.getByLabelText(/conteúdo/i)).toBeRequired();
      expect(screen.getByLabelText(/categoria/i)).toHaveValue("");
      expect(screen.getByLabelText(/tags/i)).toHaveValue("");
      expect(screen.getByLabelText(/imagem de capa/i)).toHaveValue("");

      const statusSelect = screen.getByRole("combobox", { name: /status/i });
      expect(statusSelect).toBeInTheDocument();
      expect(statusSelect).toBeRequired();

      expect(screen.getByRole("button", { name: /salvar/i })).toBeInTheDocument();
    });

    it("dado todos os campos obrigatórios preenchidos, quando salva, então chama POST /api/admin/posts e dispara onSuccess com o post criado (RF01)", async () => {
      const created = buildAdminPost({ id: "novo-post", status: "published" });
      let capturedBody: Record<string, unknown> | null = null;

      server.use(
        http.post(`${API_URL}/api/admin/posts`, async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(created, { status: 201 });
        })
      );

      const onSuccess = vi.fn();
      const user = userEvent.setup();
      render(<PostEditor mode="create" onSuccess={onSuccess} />);

      await fillForm(user, {
        title: "Como usar SDD",
        content: "Conteúdo em markdown.",
        category: "tecnologia",
        tags: "sdd, testes",
        status: "published",
      });
      await user.click(screen.getByRole("button", { name: /salvar/i }));

      await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(created));
      expect(capturedBody).toMatchObject({
        title: "Como usar SDD",
        content_markdown: "Conteúdo em markdown.",
        category_id: "tecnologia",
        tags: ["sdd", "testes"],
        status: "published",
      });
    });

    it("dado o título vazio, quando tenta salvar, então a validação HTML5 required impede o submit e a API não é chamada", async () => {
      const createSpy = vi.fn();
      server.use(
        http.post(`${API_URL}/api/admin/posts`, () => {
          createSpy();
          return HttpResponse.json(buildAdminPost(), { status: 201 });
        })
      );

      const onSuccess = vi.fn();
      const user = userEvent.setup();
      render(<PostEditor mode="create" onSuccess={onSuccess} />);

      // Preenche tudo, exceto o título (obrigatório), para isolar a causa.
      await fillForm(user, {
        content: "Conteúdo em markdown.",
        category: "tecnologia",
        status: "draft",
      });
      await user.click(screen.getByRole("button", { name: /salvar/i }));

      expect(createSpy).not.toHaveBeenCalled();
      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe("modo edit (RF03)", () => {
    it("dado um post via props, então pré-preenche todos os campos, inclusive category_id como texto livre (sem select)", () => {
      const post = buildAdminPost({
        title: "Post existente",
        content_markdown: "Conteúdo original.",
        category_id: "cultura",
        tags: ["a", "b"],
        cover_image_url: "https://exemplo.com/capa.png",
        status: "published",
      });

      render(<PostEditor mode="edit" post={post} />);

      expect(screen.getByLabelText(/título/i)).toHaveValue("Post existente");
      expect(screen.getByLabelText(/conteúdo/i)).toHaveValue("Conteúdo original.");
      expect(screen.getByLabelText(/categoria/i)).toHaveValue("cultura");
      expect(screen.getByLabelText(/imagem de capa/i)).toHaveValue(
        "https://exemplo.com/capa.png"
      );
      expect(screen.getByRole("combobox", { name: /status/i })).toHaveValue("published");

      // category_id é um campo de texto livre — não existe endpoint de
      // categorias na spec, então não deve haver um <select> para categoria.
      expect(screen.queryByRole("combobox", { name: /categoria/i })).not.toBeInTheDocument();
    });

    it("dado um post existente, quando salva alterações, então chama PUT /api/admin/posts/{id} e dispara onSuccess (RF03)", async () => {
      const post = buildAdminPost({ id: "post-42", title: "Título antigo" });
      const updated = buildAdminPost({ id: "post-42", title: "Título novo" });
      let capturedId: string | null = null;
      let capturedBody: Record<string, unknown> | null = null;

      server.use(
        http.put(`${API_URL}/api/admin/posts/:id`, async ({ request, params }) => {
          capturedId = String(params.id);
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(updated, { status: 200 });
        })
      );

      const onSuccess = vi.fn();
      const user = userEvent.setup();
      render(<PostEditor mode="edit" post={post} onSuccess={onSuccess} />);

      const titleInput = screen.getByLabelText(/título/i);
      await user.clear(titleInput);
      await user.type(titleInput, "Título novo");
      await user.click(screen.getByRole("button", { name: /salvar/i }));

      await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(updated));
      expect(capturedId).toBe("post-42");
      expect(capturedBody).toMatchObject({ title: "Título novo" });
    });
  });

  it("dado um erro de validação (422) da API, quando tenta salvar, então exibe a mensagem via role=alert sem quebrar a UI", async () => {
    server.use(
      http.post(`${API_URL}/api/admin/posts`, () =>
        HttpResponse.json({ detail: "Categoria inválida." }, { status: 422 })
      )
    );

    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<PostEditor mode="create" onSuccess={onSuccess} />);

    await fillForm(user, {
      title: "Post com erro",
      content: "Conteúdo.",
      category: "invalida",
      status: "draft",
    });
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/categoria inválida/i);
    expect(onSuccess).not.toHaveBeenCalled();
    // A UI continua íntegra: o formulário ainda está montado e utilizável.
    expect(screen.getByRole("button", { name: /salvar/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/título/i)).toHaveValue("Post com erro");
  });

  it("dado um erro inesperado (500) da API, quando tenta salvar, então exibe uma mensagem de erro via role=alert sem quebrar a UI", async () => {
    server.use(
      http.post(`${API_URL}/api/admin/posts`, () =>
        HttpResponse.json({ detail: "Erro interno do servidor." }, { status: 500 })
      )
    );

    const user = userEvent.setup();
    render(<PostEditor mode="create" />);

    await fillForm(user, {
      title: "Post com erro 500",
      content: "Conteúdo.",
      category: "tecnologia",
      status: "draft",
    });
    await user.click(screen.getByRole("button", { name: /salvar/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /salvar/i })).toBeInTheDocument();
  });

  describe("botão Cancelar", () => {
    it("não é exibido quando onCancel não é passado", () => {
      render(<PostEditor mode="create" />);

      expect(screen.queryByRole("button", { name: /cancelar/i })).not.toBeInTheDocument();
    });

    it("dado onCancel, quando clicado, então é chamado", async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();
      render(<PostEditor mode="create" onCancel={onCancel} />);

      const cancelButton = screen.getByRole("button", { name: /cancelar/i });
      expect(cancelButton).toBeInTheDocument();

      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });
});
