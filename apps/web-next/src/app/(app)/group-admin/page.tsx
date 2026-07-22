'use client';

import { useRouter } from 'next/navigation';
import AdministrationEngine from '@/components/dashboard/AdministrationEngine';
import { useSessionStore } from '@/stores/sessionStore';

export default function GroupAdminPage() {
  const router = useRouter();
  const { user } = useSessionStore();

  return (
    <AdministrationEngine
      user={user}
      onBack={() => router.push('/dashboard')}
      onViewReport={(batchId: number) => router.push(`/admin/reports/${batchId}`)}
      onViewForum={() => router.push('/discussions')}
      onViewPremium={(slugOrId: string | number) => router.push(`/profile/${slugOrId}`)}
    />
  );
}
