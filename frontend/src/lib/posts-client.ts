/**
 * Cliente HTTP fino para os endpoints de posts (SPEC-002).
 * Mesmo espírito de `api-client.ts`: nenhuma regra de negócio aqui, apenas
 * chamadas HTTP e parsing/erro de resposta.
 */

export type PostStatus = "draft" | "published";

export interface AdminPost {
  id: string;
  title: string;
  slug: string;
  content_markdown: string;
  category_id: string;
  tags: string[];
  cover_image_url: string | null;
  status: PostStatus;
  published_at: string | null;
  created_at: string;
  deleted_at: string | null;
}

export interface PublicPost {
  id: string;
  title: string;
  slug: string;
  content_markdown: string;
  category_id: string;
  tags: string[];
  cover_image_url: string | null;
  published_at: string | null;
}

export interface PostPage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PostInput {
  title: string;
  content_markdown: string;
  category_id: string;
  tags: string[];
  cover_image_url: string | null;
  status: PostStatus;
}

export interface AdminPostsQuery {
  status?: PostStatus;
  category?: string;
  q?: string;
  page?: number;
  page_size?: number;
  include_deleted?: boolean;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ErrorBody {
  detail?: string;
}

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as ErrorBody;
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

type QueryValue = string | number | boolean | undefined;

function buildQueryString(params: Record<string, QueryValue>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }

  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/posts (público) — apenas posts com status `published`.
 */
export async function listPublicPosts(page = 1, pageSize = 10): Promise<PostPage<PublicPost>> {
  const qs = buildQueryString({ page, page_size: pageSize });
  const response = await fetch(`${API_URL}/api/posts${qs}`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Não foi possível carregar os posts.");
  }

  return (await response.json()) as PostPage<PublicPost>;
}

/**
 * GET /api/posts/{slug} (público). Retorna `null` em 404 (post inexistente
 * ou não publicado) para o chamador decidir a UI (ex.: `notFound()`).
 */
export async function getPublicPostBySlug(slug: string): Promise<PublicPost | null> {
  const response = await fetch(`${API_URL}/api/posts/${encodeURIComponent(slug)}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error("Não foi possível carregar o post.");
  }

  return (await response.json()) as PublicPost;
}

/**
 * GET /api/admin/posts (auth: editor|admin).
 *
 * `cookieHeader` é opcional: em Server Components, `fetch()` não repassa
 * automaticamente os cookies do navegador — o chamador deve lê-los via
 * `cookies()` (next/headers) e passá-los aqui manualmente (mesmo padrão de
 * `getCurrentUser` em `api-client.ts`). Em Client Components, basta omitir o
 * parâmetro: `credentials: "include"` já garante o envio do cookie de
 * sessão pelo navegador.
 */
export async function listAdminPosts(
  cookieHeader?: string,
  params: AdminPostsQuery = {}
): Promise<PostPage<AdminPost>> {
  const qs = buildQueryString({
    status: params.status,
    category: params.category,
    q: params.q,
    page: params.page,
    page_size: params.page_size,
    include_deleted: params.include_deleted,
  });

  const response = await fetch(`${API_URL}/api/admin/posts${qs}`, {
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Não foi possível carregar os posts administrativos.");
  }

  return (await response.json()) as PostPage<AdminPost>;
}

/**
 * POST /api/admin/posts (auth: editor|admin). Response `201`.
 */
export async function createPost(data: PostInput): Promise<AdminPost> {
  const response = await fetch(`${API_URL}/api/admin/posts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Não foi possível criar o post."));
  }

  return (await response.json()) as AdminPost;
}

/**
 * PUT /api/admin/posts/{id} (auth: editor|admin). Campos parciais permitidos.
 */
export async function updatePost(id: string, data: Partial<PostInput>): Promise<AdminPost> {
  const response = await fetch(`${API_URL}/api/admin/posts/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Não foi possível atualizar o post."));
  }

  return (await response.json()) as AdminPost;
}

/**
 * DELETE /api/admin/posts/{id} (auth: editor|admin). Soft delete — response
 * `204` sem corpo.
 */
export async function deletePost(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/admin/posts/${encodeURIComponent(id)}`, {
    method: "DELETE",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Não foi possível excluir o post.");
  }
}
