'use client';

import { useRouter } from 'next/navigation';
import AssignmentsView from '@/components/dashboard/AssignmentsView';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

export default function AssignmentsPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  const { startBankQuiz, startCoding } = useAssessmentNav();
  return (
    <AssignmentsView
      user={user}
      onStartQuiz={startBankQuiz}
      onStartCoding={startCoding}
      onBack={() => router.push('/dashboard')}
    />
  );
}
