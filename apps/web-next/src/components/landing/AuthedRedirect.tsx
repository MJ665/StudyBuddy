'use client';

/**
 * Client island for the marketing home (`/`). Probes the session; if the visitor
 * is already logged in, it sends them straight to their role landing (preserving
 * the pre-landing behavior where "/" bounced authenticated users into the app).
 * Guests stay on the marketing page. Renders nothing.
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { landingRouteFor, useSessionStore } from '@/stores/sessionStore';

export default function AuthedRedirect() {
  const router = useRouter();
  const { user, hydrated, hydrate } = useSessionStore();

  useEffect(() => {
    if (!hydrated) void hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (hydrated && user) router.replace(landingRouteFor(user));
  }, [hydrated, user, router]);

  return null;
}
