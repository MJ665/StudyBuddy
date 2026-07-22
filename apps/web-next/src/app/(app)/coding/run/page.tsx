'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import CodeEditor from '@/components/quiz/CodeEditor';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

export default function CodingRunPage() {
  const router = useRouter();
  const { quiz } = useSessionStore();
  const { finishRun } = useAssessmentNav();

  useEffect(() => {
    if (!quiz.bank) router.replace('/dashboard');
  }, [quiz.bank, router]);

  if (!quiz.bank) return null;

  return (
    <div className="h-full w-full p-8 flex flex-col">
      <CodeEditor
        question={quiz.bank}
        onFinish={(res: Record<string, unknown>) => finishRun(res, 'coding')}
      />
    </div>
  );
}
