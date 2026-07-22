'use client';

import { useRouter } from 'next/navigation';
import Dashboard from '@/components/dashboard/Dashboard';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout, startQuiz } = useSessionStore();
  const { startBankQuiz, startDailyChallenge, startCoding } = useAssessmentNav();

  return (
    <Dashboard
      user={user}
      onLogout={() => {
        logout();
        router.replace('/login');
      }}
      onStartQuiz={startBankQuiz}
      onStartDailyChallenge={startDailyChallenge}
      onStartCoding={startCoding}
      onViewLeaderboard={(bank: Record<string, unknown>) => {
        startQuiz(bank, []); // stash bank for the leaderboard page
        router.push('/leaderboard');
      }}
      onViewProfile={() => router.push('/profile')}
      onViewForum={() => router.push('/discussions')}
      onViewAssignments={() => router.push('/assignments')}
      onViewHistory={() => router.push('/history')}
      onViewLibrary={() => router.push('/library')}
      onViewNotifications={() => router.push('/notifications')}
    />
  );
}
