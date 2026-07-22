'use client';

import { useRouter } from 'next/navigation';
import AttemptHistory from '@/components/profile/AttemptHistory';
import { useSessionStore } from '@/stores/sessionStore';

export default function HistoryPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return <AttemptHistory user={user} onBack={() => router.push('/dashboard')} />;
}
