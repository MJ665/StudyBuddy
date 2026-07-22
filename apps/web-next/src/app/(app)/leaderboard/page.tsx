'use client';

import { useRouter } from 'next/navigation';
import Leaderboard from '@/components/leaderboard/Leaderboard';
import { useSessionStore } from '@/stores/sessionStore';

export default function LeaderboardPage() {
  const router = useRouter();
  const { user, quiz } = useSessionStore();
  return (
    <Leaderboard
      bank={quiz.bank}
      user={user}
      onBack={() => router.push('/dashboard')}
    />
  );
}
