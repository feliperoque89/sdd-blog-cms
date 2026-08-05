import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/api-client";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // fetch() no servidor não repassa automaticamente os cookies do
  // navegador para outra chamada fetch — é preciso ler via cookies() e
  // anexar manualmente como header Cookie na requisição a /api/auth/me.
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore.toString());

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <p className="text-sm text-gray-700">Olá, {user.name}</p>
      </header>
      <main className="px-6 py-8">{children}</main>
    </div>
  );
}
