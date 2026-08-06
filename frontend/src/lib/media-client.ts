/**
 * Cliente HTTP fino para upload da imagem de capa (SPEC-005 / RF01).
 * Mesmo espírito de `posts-client.ts`: nenhuma regra de negócio aqui, apenas
 * a chamada HTTP e parsing de erro. Validação de tipo/tamanho é sempre
 * responsabilidade do backend — este client só encaminha o arquivo.
 */

export interface CoverImageUploadResult {
  url: string;
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

export async function uploadCoverImage(file: File): Promise<CoverImageUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/api/admin/media/cover-image`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, "Não foi possível enviar a imagem."));
  }

  return (await response.json()) as CoverImageUploadResult;
}
