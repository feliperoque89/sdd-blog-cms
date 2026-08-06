/**
 * Cliente HTTP fino para o seletor de categorias do `PostEditor` (SPEC-002 /
 * RF01). Somente leitura — não existe endpoint de criação/edição de
 * categoria (fora do escopo de SPEC-002); sem uma categoria válida,
 * `POST /api/admin/posts` sempre falhava com violação de chave estrangeira.
 */

export interface Category {
  id: string;
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
