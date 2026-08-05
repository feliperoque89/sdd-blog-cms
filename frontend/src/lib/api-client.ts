/**
 * Cliente HTTP fino para os endpoints de autenticação (SPEC-001).
 * Compartilhado por LoginForm, LogoutButton e o AdminLayout para evitar
 * duplicar URLs e parsing de resposta entre client e server components.
 */

export interface AuthenticatedUser {
  id: string;
  name: string;
  role: "admin" | "editor";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type LoginResult =
  | { ok: true; user: AuthenticatedUser }
  | { ok: false; status: number; message: string };

interface ErrorBody {
  detail?: string;
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ErrorBody;
    return body.detail ?? "Não foi possível fazer login.";
  } catch {
    return "Não foi possível fazer login.";
  }
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    return { ok: false, status: response.status, message: await extractErrorMessage(response) };
  }

  const user = (await response.json()) as AuthenticatedUser;
  return { ok: true, user };
}

export async function logout(): Promise<void> {
  await fetch(`${API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

/**
 * Uso exclusivo em Server Components: fetch() no servidor não repassa
 * automaticamente os cookies do navegador, então o chamador precisa ler o
 * cookie header via `cookies()` (next/headers) e passá-lo explicitamente.
 */
export async function getCurrentUser(cookieHeader: string): Promise<AuthenticatedUser | null> {
  const response = await fetch(`${API_URL}/api/auth/me`, {
    headers: { Cookie: cookieHeader },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as AuthenticatedUser;
}
