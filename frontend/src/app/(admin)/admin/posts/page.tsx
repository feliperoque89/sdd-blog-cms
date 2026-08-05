"use client";

import { useEffect, useState, type ChangeEvent } from "react";
import PostEditor from "@/components/PostEditor";
import { deletePost, listAdminPosts, type AdminPost, type PostStatus } from "@/lib/posts-client";

type EditingState = AdminPost | "new" | null;

export default function AdminPostsPage() {
  const [posts, setPosts] = useState<AdminPost[]>([]);
  const [statusFilter, setStatusFilter] = useState<PostStatus | "">("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [editingState, setEditingState] = useState<EditingState>(null);
  const [error, setError] = useState<string | null>(null);

  // Disparamos o fetch apenas quando o filtro de status ou a página mudam
  // por ação do usuário. `pageSize` é lido do estado (via closure) apenas
  // para compor a query — não deve, por si só, causar um novo fetch (daí
  // não constar nas deps abaixo).
  useEffect(() => {
    let cancelled = false;

    listAdminPosts(undefined, {
      status: statusFilter || undefined,
      page,
      page_size: pageSize,
    })
      .then((result) => {
        if (cancelled) {
          return;
        }
        setPosts(result.items);
        setTotal(result.total);
        setPageSize(result.page_size);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "Não foi possível carregar os posts.");
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, page]);

  function handleStatusFilterChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = event.target.value as PostStatus | "";
    setStatusFilter(value);
    setPage(1);
  }

  function handleCreateSuccess(newPost: AdminPost) {
    setPosts((prev) => [newPost, ...prev]);
    setEditingState(null);
  }

  function handleUpdateSuccess(updated: AdminPost) {
    setPosts((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    setEditingState(null);
  }

  async function handleDelete(post: AdminPost) {
    const confirmed = window.confirm(`Excluir o post "${post.title}"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deletePost(post.id);
      setPosts((prev) => prev.filter((item) => item.id !== post.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível excluir o post.");
    }
  }

  const hasNextPage = page * pageSize < total;
  const hasPrevPage = page > 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Posts</h1>
        <button
          type="button"
          onClick={() => setEditingState("new")}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white"
        >
          Novo post
        </button>
      </div>

      <div className="flex flex-col gap-1 sm:w-64">
        <label htmlFor="admin-posts-status-filter" className="text-sm font-medium text-foreground">
          Status
        </label>
        <select
          id="admin-posts-status-filter"
          value={statusFilter}
          onChange={handleStatusFilterChange}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">Todos</option>
          <option value="draft">Rascunho</option>
          <option value="published">Publicado</option>
        </select>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      {editingState !== null && (
        <div className="rounded border border-gray-200 p-4">
          {editingState === "new" ? (
            <PostEditor
              mode="create"
              onSuccess={handleCreateSuccess}
              onCancel={() => setEditingState(null)}
            />
          ) : (
            <PostEditor
              mode="edit"
              post={editingState}
              onSuccess={handleUpdateSuccess}
              onCancel={() => setEditingState(null)}
            />
          )}
        </div>
      )}

      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th scope="col" className="py-2 pr-4 font-medium text-gray-600">
              Título
            </th>
            <th scope="col" className="py-2 pr-4 font-medium text-gray-600">
              Status
            </th>
            <th scope="col" className="py-2 pr-4 font-medium text-gray-600">
              Ações
            </th>
          </tr>
        </thead>
        <tbody>
          {posts.map((post) => (
            <tr key={post.id} className="border-b border-gray-100">
              <td className="py-2 pr-4">{post.title}</td>
              <td className="py-2 pr-4">{post.status}</td>
              <td className="py-2 pr-4">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEditingState(post)}
                    className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700"
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(post)}
                    className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-red-600"
                  >
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setPage((current) => current - 1)}
          disabled={!hasPrevPage}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 disabled:opacity-50"
        >
          Anterior
        </button>
        <span className="text-sm text-gray-600">Página {page}</span>
        <button
          type="button"
          onClick={() => setPage((current) => current + 1)}
          disabled={!hasNextPage}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 disabled:opacity-50"
        >
          Próxima página
        </button>
      </div>
    </div>
  );
}
