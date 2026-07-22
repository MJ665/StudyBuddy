'use client';

import { useRouter } from 'next/navigation';
import MentorDashboard from '@/components/dashboard/MentorDashboard';
import { useSessionStore } from '@/stores/sessionStore';

export default function MentorPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  return <MentorDashboard user={user} onBack={() => router.push('/dashboard')} />;
}
