"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  createPost,
  updatePost,
  type AdminPost,
  type PostInput,
  type PostStatus,
} from "@/lib/posts-client";
import { listCategories, createCategory, type Category } from "@/lib/categories-client";
import CoverImageUpload from "@/components/CoverImageUpload";

/**
 * Valores usados para pré-preencher o formulário em modo `create` (ex.:
 * rascunho vindo do assistente de IA — SPEC-003). Ignorado em modo `edit`,
 * onde `post` já é a fonte de verdade.
 */
export interface PostEditorInitialValues {
  title?: string;
  content_markdown?: string;
  category_id?: string;
  tags?: string[];
  cover_image_url?: string | null;
  status?: PostStatus;
}

export interface PostEditorProps {
  mode: "create" | "edit";
  post?: AdminPost;
  initialValues?: PostEditorInitialValues;
  onSuccess?: (post: AdminPost) => void;
  onCancel?: () => void;
}

function parseTags(tagsInput: string): string[] {
  return tagsInput
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

export default function PostEditor({ mode, post, initialValues, onSuccess, onCancel }: PostEditorProps) {
  const [title, setTitle] = useState(post?.title ?? initialValues?.title ?? "");
  const [content, setContent] = useState(post?.content_markdown ?? initialValues?.content_markdown ?? "");
  const [category, setCategory] = useState(post?.category_id ?? initialValues?.category_id ?? "");
  const [tagsInput, setTagsInput] = useState(
    post?.tags.join(", ") ?? initialValues?.tags?.join(", ") ?? ""
  );
  const [coverImageUrl, setCoverImageUrl] = useState(
    post?.cover_image_url ?? initialValues?.cover_image_url ?? ""
  );
  const [status, setStatus] = useState<PostStatus>(post?.status ?? initialValues?.status ?? "draft");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isAddingCategory, setIsAddingCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  // RF01 exige uma categoria, mas SPEC-002 não define endpoint de gestão de
  // categorias — este seletor só lista as já cadastradas. Sem ele, o editor
  // tinha que digitar um UUID de categoria de cabeça, e o post falhava ao
  // salvar (violação de chave estrangeira) sempre que o valor não existisse.
  useEffect(() => {
    let cancelled = false;
    listCategories()
      .then((result) => {
        if (!cancelled) {
          setCategories(result);
        }
      })
      .catch(() => {
        // Falha ao carregar categorias não deve quebrar o formulário — o
        // select fica só com o placeholder até uma nova tentativa (ex.:
        // reabrir o formulário).
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError(null);
    setIsSubmitting(true);

    const payload: PostInput = {
      title,
      content_markdown: content,
      category_id: category,
      tags: parseTags(tagsInput),
      cover_image_url: coverImageUrl.trim() === "" ? null : coverImageUrl.trim(),
      status,
    };

    try {
      const result =
        mode === "edit" && post
          ? await updatePost(post.id, payload)
          : await createPost(payload);
      onSuccess?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar o post.");
    } finally {
      setIsSubmitting(false);
    }
  }

  // RF09 — cria a categoria direto na tela, sem exigir uma tela
  // administrativa separada. O backend é idempotente por nome
  // (case-insensitive): se a categoria já existir, devolve a existente em
  // vez de duplicar.
  async function handleCreateCategory() {
    const trimmedName = newCategoryName.trim();
    if (trimmedName === "") {
      setCategoryError("Informe um nome para a categoria.");
      return;
    }

    setCategoryError(null);
    setIsCreatingCategory(true);

    try {
      const created = await createCategory(trimmedName);
      setCategories((current) =>
        current.some((c) => c.id === created.id)
          ? current
          : [...current, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      setCategory(created.id);
      setNewCategoryName("");
      setIsAddingCategory(false);
    } catch (err) {
      setCategoryError(
        err instanceof Error ? err.message : "Não foi possível criar a categoria."
      );
    } finally {
      setIsCreatingCategory(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="post-title" className="text-sm font-medium text-foreground">
          Título
        </label>
        <input
          id="post-title"
          name="title"
          type="text"
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="post-content" className="text-sm font-medium text-foreground">
          Conteúdo (markdown)
        </label>
        <textarea
          id="post-content"
          name="content_markdown"
          required
          rows={10}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="post-category" className="text-sm font-medium text-foreground">
          Categoria
        </label>
        <select
          id="post-category"
          name="category_id"
          required
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">Selecione uma categoria</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        {isAddingCategory ? (
          <div className="flex items-center gap-2 pt-1">
            <label htmlFor="post-new-category-name" className="sr-only">
              Nome da nova categoria
            </label>
            <input
              id="post-new-category-name"
              name="new_category_name"
              type="text"
              placeholder="Nome da nova categoria"
              value={newCategoryName}
              onChange={(event) => setNewCategoryName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleCreateCategory();
                }
              }}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void handleCreateCategory()}
              disabled={isCreatingCategory}
              className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Adicionar
            </button>
            <button
              type="button"
              onClick={() => {
                setIsAddingCategory(false);
                setNewCategoryName("");
                setCategoryError(null);
              }}
              className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700"
            >
              Cancelar
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsAddingCategory(true)}
            className="self-start pt-1 text-sm font-medium text-blue-700 hover:underline"
          >
            + Nova categoria
          </button>
        )}
        {categoryError && (
          <p role="alert" className="text-sm text-red-600">
            {categoryError}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="post-tags" className="text-sm font-medium text-foreground">
          Tags (separadas por vírgula)
        </label>
        <input
          id="post-tags"
          name="tags"
          type="text"
          value={tagsInput}
          onChange={(event) => setTagsInput(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <CoverImageUpload
        value={coverImageUrl.trim() === "" ? null : coverImageUrl}
        onChange={(url) => setCoverImageUrl(url)}
      />

      <div className="flex flex-col gap-1">
        <label htmlFor="post-status" className="text-sm font-medium text-foreground">
          Status
        </label>
        <select
          id="post-status"
          name="status"
          required
          value={status}
          onChange={(event) => setStatus(event.target.value as PostStatus)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="draft">Rascunho</option>
          <option value="published">Publicado</option>
        </select>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Salvar
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700"
          >
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
