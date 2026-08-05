import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Checagem otimista de sessão para rotas /admin/*: apenas confirma a
 * presença do cookie access_token. A validade do JWT (assinatura,
 * expiração) só pode ser verificada pelo backend, já que o segredo de
 * assinatura nunca fica disponível no processo do frontend — a checagem
 * autoritativa (que cobre token expirado/inválido) acontece em
 * src/app/(admin)/layout.tsx via GET /api/auth/me.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAdminRoute = pathname === "/admin" || pathname.startsWith("/admin/");

  if (isAdminRoute && !request.cookies.has("access_token")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
