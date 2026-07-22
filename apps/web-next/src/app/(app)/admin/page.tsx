'use client';

import { useRouter } from 'next/navigation';
import LDAdminDashboard from '@/components/dashboard/LDAdminDashboard';
import { useSessionStore } from '@/stores/sessionStore';

export default function AdminPage() {
  const router = useRouter();
  const { user, logout } = useSessionStore();

  return (
    <LDAdminDashboard
      user={user}
      onLogout={() => {
        logout();
        router.replace('/login');
      }}
      onViewReport={(id: number) => router.push(`/admin/reports/${id}`)}
      onViewPremium={(slugOrId: string | number) => router.push(`/profile/${slugOrId}`)}
    />
  );
}
