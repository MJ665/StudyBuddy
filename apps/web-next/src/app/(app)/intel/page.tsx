'use client';

import { useRouter } from 'next/navigation';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import UserIntelPanel from '@/components/dashboard/UserIntelPanel';
import { useSessionStore } from '@/stores/sessionStore';

function IntelInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { user } = useSessionStore();
  const userId = params.get('userId');
  return (
    <UserIntelPanel
      userId={userId ? Number(userId) : user?.id}
      onClose={() => router.push('/dashboard')}
    />
  );
}

export default function IntelPage() {
  return (
    <Suspense fallback={null}>
      <IntelInner />
    </Suspense>
  );
}
