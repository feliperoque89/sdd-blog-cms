import Link from "next/link";

export default function AdminDashboardPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Painel administrativo</h1>
      <Link
        href="/admin/posts"
        className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white"
      >
        Gerenciar posts
      </Link>
    </div>
  );
}
