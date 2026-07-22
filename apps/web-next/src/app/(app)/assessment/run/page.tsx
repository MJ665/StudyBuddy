'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import QuizFlow from '@/components/quiz/QuizFlow';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

export default function AssessmentRunPage() {
  const router = useRouter();
  const { user, quiz } = useSessionStore();
  const { finishRun } = useAssessmentNav();

  // Deep-linking an empty run (refresh mid-quiz) has no questions to show —
  // return to the dashboard rather than rendering a broken flow.
  useEffect(() => {
    if (!quiz.bank || quiz.questions.length === 0) router.replace('/dashboard');
  }, [quiz, router]);

  if (!quiz.bank || quiz.questions.length === 0) return null;

  return (
    <QuizFlow
      bank={quiz.bank}
      questions={quiz.questions}
      user={user}
      onFinish={(result: { submitResult?: Record<string, unknown>; timeTaken: number }) =>
        finishRun(
          result.submitResult
            ? { ...result.submitResult, timeTaken: result.timeTaken }
            : null,
          'quiz',
        )
      }
      onCancel={() => router.push('/dashboard')}
    />
  );
}
