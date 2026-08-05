import Link from "next/link";
import { listPublicPosts } from "@/lib/posts-client";

interface HomePageProps {
  searchParams: Promise<{ page?: string }>;
}

function parsePage(pageParam: string | undefined): number {
  if (!pageParam) {
    return 1;
  }

  const parsed = Number(pageParam);
  return Number.isNaN(parsed) || parsed < 1 ? 1 : parsed;
}

export default async function HomePage({ searchParams }: HomePageProps) {
  const { page: pageParam } = await searchParams;
  const page = parsePage(pageParam);
  const pageSize = 10;

  const { items, total } = await listPublicPosts(page, pageSize);

  const hasPrevPage = page > 1;
  const hasNextPage = page * pageSize < total;

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">SDD Blog CMS</h1>
      <p className="mt-2 text-gray-600">Posts publicados no blog.</p>

      <ul className="mt-8 flex flex-col gap-6">
        {items.map((post) => (
          <li key={post.id}>
            <Link
              href={`/posts/${post.slug}`}
              className="text-lg font-semibold text-blue-700 hover:underline"
            >
              {post.title}
            </Link>
          </li>
        ))}
      </ul>

      <nav className="mt-8 flex items-center justify-between text-sm">
        {hasPrevPage ? (
          <Link href={`/?page=${page - 1}`} className="font-medium text-blue-700 hover:underline">
            Anterior
          </Link>
        ) : (
          <span />
        )}
        {hasNextPage ? (
          <Link href={`/?page=${page + 1}`} className="font-medium text-blue-700 hover:underline">
            Próxima página
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </main>
  );
}
