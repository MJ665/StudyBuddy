'use client';

/**
 * Root route (Phase 4 rebuild).
 *
 * The 507-line single-page state machine that lived here is gone — every
 * view is now a real URL under src/app/(app)/ and src/app/(public)/.
 * "/" simply lands the user where their role belongs.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { landingRouteFor, useSessionStore } from '@/stores/sessionStore';

export default function RootRedirect() {
  const router = useRouter();
  const { user, hydrated, hydrate } = useSessionStore();

  useEffect(() => {
    if (!hydrated) void hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (hydrated) router.replace(landingRouteFor(user));
  }, [hydrated, user, router]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
