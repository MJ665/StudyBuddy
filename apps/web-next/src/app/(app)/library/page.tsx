'use client';

import { useRouter } from 'next/navigation';
import QuestionLibrary from '@/components/dashboard/QuestionLibrary';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

export default function LibraryPage() {
  const router = useRouter();
  const { user } = useSessionStore();
  const { startBankQuiz } = useAssessmentNav();
  return (
    <QuestionLibrary
      user={user}
      onStartQuiz={startBankQuiz}
      onBack={() => router.push('/dashboard')}
    />
  );
}
