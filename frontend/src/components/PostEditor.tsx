"use client";

import { useState, type FormEvent } from "react";
import {
  createPost,
  updatePost,
  type AdminPost,
  type PostInput,
  type PostStatus,
} from "@/lib/posts-client";

export interface PostEditorProps {
  mode: "create" | "edit";
  post?: AdminPost;
  onSuccess?: (post: AdminPost) => void;
  onCancel?: () => void;
}

function parseTags(tagsInput: string): string[] {
  return tagsInput
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

export default function PostEditor({ mode, post, onSuccess, onCancel }: PostEditorProps) {
  const [title, setTitle] = useState(post?.title ?? "");
  const [content, setContent] = useState(post?.content_markdown ?? "");
  const [category, setCategory] = useState(post?.category_id ?? "");
  const [tagsInput, setTagsInput] = useState(post?.tags.join(", ") ?? "");
  const [coverImageUrl, setCoverImageUrl] = useState(post?.cover_image_url ?? "");
  const [status, setStatus] = useState<PostStatus>(post?.status ?? "draft");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
        <input
          id="post-category"
          name="category_id"
          type="text"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
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

      <div className="flex flex-col gap-1">
        <label htmlFor="post-cover-image" className="text-sm font-medium text-foreground">
          Imagem de capa (URL, opcional)
        </label>
        <input
          id="post-cover-image"
          name="cover_image_url"
          type="text"
          value={coverImageUrl}
          onChange={(event) => setCoverImageUrl(event.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

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
