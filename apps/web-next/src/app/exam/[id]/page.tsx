'use client';

import 'katex/dist/katex.min.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import ApiService from '@/services/ApiService';
import QuestionCard, { QCard } from '@/components/quiz/cards/QuestionCard';

interface Paper {
  attempt_id: number;
  title: string;
  proctoring_mode: string;
  deadline: string;
  questions: QCard[];
}
interface Result {
  score: number; total: number; percent: number; passed: boolean; status: string; flags: number;
}

function fmtTime(ms: number): string {
  if (ms < 0) ms = 0;
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

export default function ExamRunnerPage() {
  const params = useParams();
  const examId = Number(Array.isArray(params.id) ? params.id[0] : params.id);

  const [paper, setPaper] = useState<Paper | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number>(0);
  const [flags, setFlags] = useState<number>(0);
  const [consent, setConsent] = useState(false);
  const submittingRef = useRef(false);

  // Start the exam.
  useEffect(() => {
    ApiService.startExam(examId)
      .then((p: Paper) => setPaper(p))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not start exam'));
  }, [examId]);

  const submit = useCallback(async () => {
    if (!paper || submittingRef.current || result) return;
    submittingRef.current = true;
    try {
      const r = await ApiService.submitExam(paper.attempt_id, answers);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submit failed');
      submittingRef.current = false;
    }
  }, [paper, answers, result]);

  // Countdown timer → auto-submit at deadline.
  useEffect(() => {
    if (!paper || result) return;
    const dl = new Date(paper.deadline).getTime();
    const t = setInterval(() => {
      const rem = dl - Date.now();
      setRemaining(rem);
      if (rem <= 0) {
        clearInterval(t);
        submit();
      }
    }, 1000);
    return () => clearInterval(t);
  }, [paper, result, submit]);

  // Proctoring: integrity listeners (Standard) → POST proctor-event + flag.
  useEffect(() => {
    if (!paper || result || paper.proctoring_mode === 'none') return;
    const flag = (event_type: string, detail?: string) => {
      setFlags((f) => f + 1);
      ApiService.logProctorEvent(paper.attempt_id, event_type, detail).catch(() => {});
    };
    const onVis = () => document.hidden && flag('tab_switch');
    const onBlur = () => flag('focus_loss');
    const onCopy = () => flag('copy');
    const onPaste = () => flag('paste');
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('blur', onBlur);
    document.addEventListener('copy', onCopy);
    document.addEventListener('paste', onPaste);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('paste', onPaste);
    };
  }, [paper, result]);

  // Advanced proctoring: webcam consent + periodic snapshots.
  useEffect(() => {
    if (!paper || result || paper.proctoring_mode !== 'advanced' || !consent) return;
    let stream: MediaStream | null = null;
    let interval: ReturnType<typeof setInterval> | null = null;
    navigator.mediaDevices?.getUserMedia({ video: true })
      .then((s) => {
        stream = s;
        interval = setInterval(() => {
          ApiService.logProctorEvent(paper.attempt_id, 'webcam_snapshot', 'periodic').catch(() => {});
        }, 30000);
      })
      .catch(() => ApiService.logProctorEvent(paper.attempt_id, 'webcam_snapshot', 'denied').catch(() => {}));
    return () => {
      if (interval) clearInterval(interval);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [paper, result, consent]);

  if (error) return <div className="min-h-screen bg-slate-950 text-rose-400 flex items-center justify-center p-8">{error}</div>;
  if (!paper) return <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">Preparing exam…</div>;

  if (result) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className={`text-5xl font-black mb-2 ${result.passed ? 'text-emerald-400' : 'text-rose-400'}`}>{result.percent}%</div>
          <div className="text-xl font-bold mb-4">{result.passed ? 'Passed' : 'Not passed'}</div>
          <div className="text-slate-400 text-sm">Score {result.score}/{result.total} · status {result.status} · {result.flags} integrity flag(s)</div>
        </div>
      </div>
    );
  }

  const needsConsent = paper.proctoring_mode === 'advanced' && !consent;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-3xl mx-auto flex items-center justify-between px-5 py-3">
          <div className="font-bold truncate">{paper.title}</div>
          <div className="flex items-center gap-4 text-sm">
            {flags > 0 && <span className="text-amber-400">⚠ {flags} flag{flags > 1 ? 's' : ''}</span>}
            <span className={`font-mono font-bold ${remaining < 60000 ? 'text-rose-400' : 'text-emerald-400'}`}>{fmtTime(remaining)}</span>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto p-5">
        {needsConsent && (
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-6 mb-6">
            <h2 className="font-bold mb-2">Proctored exam — consent required</h2>
            <p className="text-slate-400 text-sm mb-4">This exam uses webcam monitoring. By continuing you consent to periodic snapshots and integrity monitoring (tab-switch, copy/paste, focus loss are flagged).</p>
            <button onClick={() => setConsent(true)} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-bold text-sm">I consent — start</button>
          </div>
        )}

        {!needsConsent && (
          <>
            {paper.questions.map((q, i) => (
              <QuestionCard
                key={q.id}
                q={q}
                index={i}
                value={answers[String(q.id)] ?? (q.question_type === 'mcq_multi' ? [] : '')}
                onChange={(v) => setAnswers((a) => ({ ...a, [String(q.id)]: v }))}
              />
            ))}
            <button onClick={submit} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-3 font-bold mt-2">Submit exam</button>
            <p className="text-center text-slate-600 text-xs mt-4">Powered by StudyBuddy</p>
          </>
        )}
      </div>
    </div>
  );
}
