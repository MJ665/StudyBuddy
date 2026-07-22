import { redirect } from 'next/navigation';

/** Legacy short URL alias: /p/<slug> → /profile/<slug>. */
export default async function LegacyProfileAlias({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  redirect(`/profile/${slug}`);
}
