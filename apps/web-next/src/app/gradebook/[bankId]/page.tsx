'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ApiService from '@/services/ApiService';

interface GradeRow { user_id: number; user_name: string; best_score: number; best_total: number; best_pct: number; attempts: number }
interface Item { question_id: number; question: string; difficulty: number; discrimination: number; flag: string; responses: number }

const FLAG_STYLE: Record<string, string> = {
  ok: 'text-emerald-400',
  too_easy: 'text-sky-400',
  too_hard: 'text-rose-400',
  poor_discrimination: 'text-amber-400',
};

export default function GradebookPage() {
  const params = useParams();
  const bankId = Number(Array.isArray(params.bankId) ? params.bankId[0] : params.bankId);

  const [bank, setBank] = useState<string>('');
  const [grades, setGrades] = useState<GradeRow[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [responses, setResponses] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'grades' | 'items'>('grades');

  useEffect(() => {
    (async () => {
      try {
        const [gb, ia] = await Promise.all([ApiService.gradebook(bankId), ApiService.itemAnalysis(bankId)]);
        setBank(gb.bank);
        setGrades(gb.gradebook || []);
        setItems(ia.items || []);
        setResponses(ia.responses || 0);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load gradebook');
      } finally {
        setLoading(false);
      }
    })();
  }, [bankId]);

  const exportCsv = async () => {
    try {
      const csv = await ApiService.downloadGradebookCsv(bankId);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `gradebook_bank_${bankId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black">Gradebook</h1>
            <p className="text-slate-400 text-sm">{bank || `Bank #${bankId}`} · {responses} response(s)</p>
          </div>
          <button onClick={exportCsv} className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">Export CSV</button>
        </header>

        <div className="flex gap-2 mb-5">
          {(['grades', 'items'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 rounded-lg text-sm font-bold ${tab === t ? 'bg-emerald-600' : 'bg-slate-800 text-slate-400'}`}>
              {t === 'grades' ? 'Grades' : 'Item analysis'}
            </button>
          ))}
        </div>

        {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm mb-4">{error}</div>}
        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : tab === 'grades' ? (
          <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
            <div className="grid grid-cols-4 gap-2 px-4 py-3 text-xs uppercase tracking-widest text-slate-500 border-b border-slate-800">
              <span className="col-span-2">Learner</span><span>Best</span><span>Attempts</span>
            </div>
            {grades.length === 0 && <div className="p-4 text-slate-500 text-sm">No attempts yet.</div>}
            {grades.map((g) => (
              <div key={g.user_id} className="grid grid-cols-4 gap-2 px-4 py-2.5 border-b border-slate-800/50 text-sm">
                <span className="col-span-2 truncate">{g.user_name || `User ${g.user_id}`}</span>
                <span className={g.best_pct >= 40 ? 'text-emerald-400' : 'text-rose-400'}>{g.best_pct}% ({g.best_score}/{g.best_total})</span>
                <span className="text-slate-400">{g.attempts}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
            <div className="grid grid-cols-6 gap-2 px-4 py-3 text-xs uppercase tracking-widest text-slate-500 border-b border-slate-800">
              <span className="col-span-3">Question</span><span>Difficulty</span><span>Discrim.</span><span>Flag</span>
            </div>
            {items.length === 0 && <div className="p-4 text-slate-500 text-sm">Not enough data for item analysis.</div>}
            {items.map((it) => (
              <div key={it.question_id} className="grid grid-cols-6 gap-2 px-4 py-2.5 border-b border-slate-800/50 text-sm">
                <span className="col-span-3 truncate text-slate-300">{it.question || `Q${it.question_id}`}</span>
                <span className="text-slate-400">{(it.difficulty * 100).toFixed(0)}%</span>
                <span className="text-slate-400">{it.discrimination.toFixed(2)}</span>
                <span className={`font-bold ${FLAG_STYLE[it.flag] || 'text-slate-400'}`}>{it.flag}</span>
              </div>
            ))}
          </div>
        )}
        <p className="text-center text-slate-600 text-xs mt-6">Powered by StudyBuddy</p>
      </div>
    </div>
  );
}
