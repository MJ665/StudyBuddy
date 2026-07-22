'use client';

import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import ResetPasswordPage from '@/components/auth/ResetPasswordPage';

function ResetInner() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get('email') ?? undefined;
  const groupId = params.get('groupId');

  return (
    <ResetPasswordPage
      email={email}
      groupId={groupId ? Number(groupId) : undefined}
      onBack={() => router.push('/login')}
      onSuccess={() => router.push('/login')}
    />
  );
}

export default function ResetPasswordRoute() {
  return (
    <Suspense fallback={null}>
      <ResetInner />
    </Suspense>
  );
}
