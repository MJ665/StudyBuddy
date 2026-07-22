'use client';

import { useRouter } from 'next/navigation';
import NotificationsView from '@/components/dashboard/NotificationsView';
import { useSessionStore } from '@/stores/sessionStore';

export default function NotificationsPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return (
    <NotificationsView
      user={user}
      onBack={() => router.push('/dashboard')}
      onNavigate={(type: string) =>
        type === 'new_assignment' && router.push('/assignments')
      }
    />
  );
}
