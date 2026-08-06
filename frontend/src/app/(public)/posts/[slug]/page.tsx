import { notFound } from "next/navigation";
import { getPublicPostBySlug } from "@/lib/posts-client";

interface PostPageProps {
  params: Promise<{ slug: string }>;
}

export default async function PostPage({ params }: PostPageProps) {
  const { slug } = await params;
  const post = await getPublicPostBySlug(slug);

  if (!post) {
    notFound();
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="text-3xl font-bold">{post.title}</h1>
      {post.cover_image_url && (
        // eslint-disable-next-line @next/next/no-img-element -- URL vem do MinIO/S3 (host dinâmico por ambiente), não do domínio de imagens otimizadas do Next.
        <img
          src={post.cover_image_url}
          alt={post.title}
          className="mt-6 w-full rounded object-cover"
        />
      )}
      <div className="mt-6 whitespace-pre-wrap text-gray-800">{post.content_markdown}</div>
    </main>
  );
}
