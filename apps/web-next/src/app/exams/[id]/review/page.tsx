'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ApiService from '@/services/ApiService';

interface Attempt {
  id: number;
  user_id: number;
  status: string;
  score: number | null;
  total: number | null;
  passed: boolean | null;
  flags: number;
  submitted_at: string | null;
}

export default function ProctorReviewPage() {
  const params = useParams();
  const examId = Number(Array.isArray(params.id) ? params.id[0] : params.id);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ApiService.examAttemptsForReview(examId)
      .then((r) => setAttempts(r.attempts || []))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [examId]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black">Proctor review</h1>
            <p className="text-slate-400 text-sm">Exam #{examId} · attempts &amp; integrity flags</p>
          </div>
          <a href="/exams" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Exams</a>
        </header>

        {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm mb-4">{error}</div>}

        <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-x-auto">
          <div className="min-w-[560px]">
          <div className="grid grid-cols-5 gap-2 px-4 py-3 text-xs uppercase tracking-widest text-slate-500 border-b border-slate-800">
            <span>User</span><span>Status</span><span>Score</span><span>Result</span><span>Flags</span>
          </div>
          {loading ? <div className="p-4 text-slate-500 text-sm">Loading…</div> : attempts.length === 0 ? (
            <div className="p-4 text-slate-500 text-sm">No attempts yet.</div>
          ) : attempts.map((a) => (
            <div key={a.id} className="grid grid-cols-5 gap-2 px-4 py-2.5 border-b border-slate-800/50 text-sm items-center">
              <span>User {a.user_id}</span>
              <span className="text-slate-400">{a.status}</span>
              <span>{a.score != null ? `${a.score}/${a.total}` : '—'}</span>
              <span className={a.passed ? 'text-emerald-400' : a.passed === false ? 'text-rose-400' : 'text-slate-500'}>
                {a.passed == null ? '—' : a.passed ? 'Pass' : 'Fail'}
              </span>
              <span className={a.flags > 0 ? 'text-amber-400 font-bold' : 'text-slate-500'}>{a.flags > 0 ? `⚠ ${a.flags}` : '0'}</span>
            </div>
          ))}
          </div>
        </div>
        <p className="text-center text-slate-600 text-xs mt-6">Powered by StudyBuddy</p>
      </div>
    </div>
  );
}
