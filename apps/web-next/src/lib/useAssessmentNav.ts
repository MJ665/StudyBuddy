'use client';

/**
 * Shared navigation handlers for starting/finishing assessments (Phase 4).
 * One implementation of the wiring the old state machine repeated across
 * views: fetch questions → stash in the session store → navigate.
 */

import { useRouter } from 'next/navigation';
import ApiService from '@/services/ApiService';
import { useToast } from '@/components/ui/Toast';
import { useSessionStore } from '@/stores/sessionStore';

export function useAssessmentNav() {
  const router = useRouter();
  const { toast } = useToast();
  const { startQuiz, finishQuiz } = useSessionStore();

  const startBankQuiz = async (bank: { id: number; [k: string]: unknown }, maxQuestions: number) => {
    try {
      const questions = await ApiService.getQuizQuestions(bank.id, maxQuestions);
      startQuiz(bank, questions);
      router.push('/assessment/run');
    } catch (err: unknown) {
      toast('error', `Failed to start quiz: ${err instanceof Error ? err.message : 'unknown error'}`);
    }
  };

  const startDailyChallenge = (challenge: { question: { bank_id: number; [k: string]: unknown } }) => {
    startQuiz({ name: 'Daily Challenge', id: challenge.question.bank_id }, [challenge.question]);
    router.push('/assessment/run');
  };

  const startCoding = (question: Record<string, unknown>) => {
    startQuiz(question, []);
    router.push('/coding/run');
  };

  const finishRun = (result: Record<string, unknown> | null, kind: 'quiz' | 'coding' = 'quiz') => {
    if (!result) {
      toast('error', 'Failed to submit: no result returned.');
      return;
    }
    finishQuiz(result);
    router.push(kind === 'quiz' ? '/assessment/result' : '/coding/result');
  };

  return { startBankQuiz, startDailyChallenge, startCoding, finishRun };
}
