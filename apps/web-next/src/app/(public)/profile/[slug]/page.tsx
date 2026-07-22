'use client';

/**
 * Public member profile — viewable anonymously (owner decision: public
 * profiles stay). Matches the old /profile/<slug> pushState URLs.
 */

import { use } from 'react';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import PublicProfile from '@/components/profile/PublicProfile';
import { landingRouteFor, useSessionStore } from '@/stores/sessionStore';

export default function PublicProfileRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const router = useRouter();
  const { slug } = use(params);
  const { user, hydrated, hydrate } = useSessionStore();

  useEffect(() => {
    if (!hydrated) void hydrate();
  }, [hydrated, hydrate]);

  return (
    <PublicProfile
      slug={slug}
      isLoggedIn={!!user}
      onLoginClick={() => router.push('/login')}
      onBack={() => router.push(user ? landingRouteFor(user) : '/login')}
    />
  );
}
