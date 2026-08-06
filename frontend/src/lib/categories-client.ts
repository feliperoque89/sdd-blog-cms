/**
 * Cliente HTTP fino para o seletor de categorias do `PostEditor` (SPEC-002 /
 * RF08/RF09): lista categorias existentes e permite cadastrar uma nova
 * direto na tela — sem uma categoria válida, `POST /api/admin/posts` sempre
 * falhava com violação de chave estrangeira.
 */

export interface Category {
  id: string;
  name: string;
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

export async function listCategories(): Promise<Category[]> {
  const response = await fetch(`${API_URL}/api/admin/categories`, {
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Não foi possível carregar as categorias.");
  }

  return (await response.json()) as Category[];
}

/**
 * `POST /api/admin/categories` (RF09). Idempotente por nome
 * (case-insensitive) no backend — chamar com um nome já existente retorna a
 * categoria existente em vez de criar uma duplicata.
 */
export async function createCategory(name: string): Promise<Category> {
  const response = await fetch(`${API_URL}/api/admin/categories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Não foi possível criar a categoria."));
  }

  return (await response.json()) as Category;
}
