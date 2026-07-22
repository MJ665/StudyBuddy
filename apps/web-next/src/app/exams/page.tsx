'use client';

import { useEffect, useState } from 'react';
import ApiService from '@/services/ApiService';

interface Exam {
  id: number;
  title: string;
  duration_minutes: number;
  question_count: number;
  proctoring_mode: string;
  is_published: boolean;
}

const input = 'w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:border-emerald-500';
const label = 'block text-slate-400 text-[11px] uppercase tracking-widest mb-1';

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // create form
  const [title, setTitle] = useState('');
  const [bankId, setBankId] = useState('');
  const [duration, setDuration] = useState('60');
  const [passing, setPassing] = useState('40');
  const [proctoring, setProctoring] = useState('standard');
  const [publish, setPublish] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await ApiService.listExams();
      setExams(r.exams || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load exams');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await ApiService.createExam({
        title,
        bank_id: bankId ? Number(bankId) : undefined,
        duration_minutes: Number(duration),
        passing_score: Number(passing),
        proctoring_mode: proctoring,
        is_published: publish,
      });
      setShowCreate(false);
      setTitle(''); setBankId('');
      await load();
    } catch (e2: unknown) {
      setError(e2 instanceof Error ? e2.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black">Exams</h1>
            <p className="text-slate-400 text-sm">Proctored assessments · Powered by StudyBuddy</p>
          </div>
          <div className="flex gap-2">
            <a href="/" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Portal</a>
            <button onClick={() => setShowCreate((s) => !s)} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-bold">{showCreate ? 'Cancel' : 'New exam'}</button>
          </div>
        </header>

        {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm mb-4">{error}</div>}

        {showCreate && (
          <form onSubmit={create} className="rounded-xl bg-slate-900 border border-slate-800 p-5 mb-6 grid md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className={label}>Title</label><input className={input} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} /></div>
            <div><label className={label}>Question bank ID</label><input className={input} value={bankId} onChange={(e) => setBankId(e.target.value)} placeholder="draws all questions from this bank" /></div>
            <div><label className={label}>Duration (minutes)</label><input type="number" className={input} value={duration} onChange={(e) => setDuration(e.target.value)} min={1} required /></div>
            <div><label className={label}>Passing score (%)</label><input type="number" className={input} value={passing} onChange={(e) => setPassing(e.target.value)} min={0} max={100} required /></div>
            <div>
              <label className={label}>Proctoring</label>
              <select className={input} value={proctoring} onChange={(e) => setProctoring(e.target.value)}>
                <option value="none">None</option>
                <option value="standard">Standard (tab/copy/focus flags)</option>
                <option value="advanced">Advanced (+ webcam)</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} className="accent-emerald-500" /> Publish immediately</label>
            <button disabled={creating} className="md:col-span-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2.5 font-bold disabled:opacity-50">{creating ? 'Creating…' : 'Create exam'}</button>
          </form>
        )}

        <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
          {loading ? <div className="p-5 text-slate-500">Loading…</div> : exams.length === 0 ? (
            <div className="p-5 text-slate-500 text-sm">No exams yet. Create one above.</div>
          ) : exams.map((ex) => (
            <div key={ex.id} className="flex items-center justify-between gap-4 p-4 border-b border-slate-800/50">
              <div className="min-w-0">
                <div className="font-semibold truncate">{ex.title}</div>
                <div className="text-slate-500 text-xs">{ex.question_count} questions · {ex.duration_minutes} min · proctoring: {ex.proctoring_mode} {ex.is_published ? '' : '· draft'}</div>
              </div>
              <div className="flex gap-2 shrink-0">
                <a href={`/exam/${ex.id}`} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-bold">Take</a>
                <a href={`/exams/${ex.id}/review`} className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold">Review</a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
