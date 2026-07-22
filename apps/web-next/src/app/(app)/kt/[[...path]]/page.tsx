'use client';

/**
 * KT sub-app under a real route (Phase 4). KTNavShell keeps its internal
 * ktNavStore navigation; the catch-all preserves deep links like
 * /kt/company/{id}/project/{id} exactly as the old pathname-parsing did.
 */

import { useRouter } from 'next/navigation';
import KTNavShell from '@/components/kt/KTNavShell';
import KTViewport from '@/components/kt/KTViewport';
import { useSessionStore } from '@/stores/sessionStore';

export default function KTPage() {
  const router = useRouter();
  const { user } = useSessionStore();

  return (
    <KTNavShell user={user} onBack={() => router.push('/dashboard')}>
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <KTViewport user={user} />
      </div>
    </KTNavShell>
  );
}
