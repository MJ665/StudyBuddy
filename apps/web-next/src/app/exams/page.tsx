'use client';

import { useEffect, useMemo, useState } from 'react';
import ApiService from '@/services/ApiService';
import { SkeletonList } from '@/components/ui/Skeleton';
import BankCreationModal from '@/components/dashboard/BankCreationModal';
import type { UserMe } from '@/services/apiShared';

interface Exam {
  id: number;
  title: string;
  duration_minutes: number;
  question_count: number;
  proctoring_mode: string;
  is_published: boolean;
}

interface Bank {
  id: number;
  name: string;
  course_id?: number;
  question_count?: number;
}

const input = 'w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:border-emerald-500';
const label = 'block text-slate-400 text-[11px] uppercase tracking-widest mb-1';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // context for the bank picker + create-bank wizard
  const [me, setMe] = useState<UserMe | null>(null);
  const [banks, setBanks] = useState<Bank[]>([]);
  const [courses, setCourses] = useState<{ id: number; name: string }[]>([]);
  const [showBankWizard, setShowBankWizard] = useState(false);

  // create form
  const [title, setTitle] = useState('');
  const [bankId, setBankId] = useState<number | ''>('');
  const [bankSearch, setBankSearch] = useState('');
  const [duration, setDuration] = useState('60');
  const [passing, setPassing] = useState('40');
  const [proctoring, setProctoring] = useState('standard');
  const [publish, setPublish] = useState(true);

  // recipient email chips
  const [recipients, setRecipients] = useState<string[]>([]);
  const [emailInput, setEmailInput] = useState('');

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

  const loadBanks = async () => {
    try {
      const r = await ApiService.getBanks(undefined, 1, 200);
      setBanks((r?.items || []) as Bank[]);
    } catch {
      // A picker with no banks still lets the user create one inline.
      setBanks([]);
    }
  };

  useEffect(() => {
    load();
    loadBanks();
    ApiService.getMe()
      .then((u) => {
        setMe(u);
        if (u?.group_id) {
          ApiService.getCourses(u.group_id)
            .then((c) => setCourses(Array.isArray(c) ? c : (c?.courses || c?.items || [])))
            .catch(() => setCourses([]));
        }
      })
      .catch(() => setMe(null));
  }, []);

  const filteredBanks = useMemo(() => {
    const q = bankSearch.trim().toLowerCase();
    const list = q ? banks.filter((b) => b.name?.toLowerCase().includes(q)) : banks;
    return list.slice(0, 40);
  }, [banks, bankSearch]);

  const selectedBank = banks.find((b) => b.id === bankId);

  const addEmail = (raw: string) => {
    const val = raw.trim().toLowerCase();
    if (!val) return;
    if (!EMAIL_RE.test(val)) { setError(`"${val}" is not a valid email`); return; }
    if (recipients.includes(val)) { setEmailInput(''); return; }
    setRecipients((prev) => [...prev, val]);
    setEmailInput('');
    setError(null);
  };

  const onEmailKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      e.preventDefault();
      addEmail(emailInput);
    } else if (e.key === 'Backspace' && !emailInput && recipients.length) {
      setRecipients((prev) => prev.slice(0, -1));
    }
  };

  const resetForm = () => {
    setTitle(''); setBankId(''); setBankSearch('');
    setRecipients([]); setEmailInput('');
    setDuration('60'); setPassing('40'); setProctoring('standard'); setPublish(true);
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bankId) { setError('Select a question bank (or create one).'); return; }
    setCreating(true);
    setError(null);
    try {
      // If the input still holds a typed-but-unconfirmed email, include it.
      const pending = emailInput.trim().toLowerCase();
      const finalRecipients = pending && EMAIL_RE.test(pending) && !recipients.includes(pending)
        ? [...recipients, pending]
        : recipients;

      const res = await ApiService.createExam({
        title,
        bank_id: Number(bankId),
        duration_minutes: Number(duration),
        passing_score: Number(passing),
        proctoring_mode: proctoring,
        is_published: publish,
        recipient_emails: finalRecipients,
      });
      setShowCreate(false);
      resetForm();
      await load();
      if (publish && finalRecipients.length) {
        const n = res?.invited ?? 0;
        setError(null);
        // A lightweight inline confirmation (no toast system on this standalone page).
        setNotice(`Exam published — ${n} recipient${n === 1 ? '' : 's'} notified by email.`);
      }
    } catch (e2: unknown) {
      setError(e2 instanceof Error ? e2.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between mb-6 gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-black">Exams</h1>
            <p className="text-slate-400 text-sm">Proctored assessments · Powered by StudyBuddy</p>
          </div>
          <div className="flex gap-2">
            <a href="/" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Portal</a>
            <button onClick={() => { setShowCreate((s) => !s); setError(null); setNotice(null); }} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-bold">{showCreate ? 'Cancel' : 'New exam'}</button>
          </div>
        </header>

        {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm mb-4">{error}</div>}
        {notice && <div className="rounded-lg bg-emerald-500/10 text-emerald-400 p-4 text-sm mb-4">{notice}</div>}

        {showCreate && (
          <form onSubmit={create} className="rounded-xl bg-slate-900 border border-slate-800 p-5 mb-6 grid md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className={label}>Title</label><input className={input} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} /></div>

            {/* Searchable bank picker + inline create-bank wizard */}
            <div className="md:col-span-2">
              <div className="flex items-center justify-between mb-1">
                <label className={label + ' mb-0'}>Question bank</label>
                <button type="button" onClick={() => setShowBankWizard(true)} className="text-[11px] font-bold text-emerald-400 hover:text-emerald-300">+ Create new bank</button>
              </div>
              {selectedBank ? (
                <div className="flex items-center justify-between gap-3 rounded-lg bg-slate-800 border border-emerald-600/50 px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold truncate">{selectedBank.name}</div>
                    <div className="text-[11px] text-slate-500">{selectedBank.question_count ?? '—'} questions · draws all questions from this bank</div>
                  </div>
                  <button type="button" onClick={() => { setBankId(''); setBankSearch(''); }} className="text-xs text-slate-400 hover:text-white shrink-0">Change</button>
                </div>
              ) : (
                <>
                  <input className={input} value={bankSearch} onChange={(e) => setBankSearch(e.target.value)} placeholder="Search banks by name…" />
                  <div className="mt-2 max-h-52 overflow-y-auto rounded-lg border border-slate-800 divide-y divide-slate-800/60">
                    {filteredBanks.length === 0 ? (
                      <div className="px-3 py-3 text-xs text-slate-500">No banks found. Use “Create new bank”.</div>
                    ) : filteredBanks.map((b) => (
                      <button type="button" key={b.id} onClick={() => setBankId(b.id)} className="w-full text-left px-3 py-2 hover:bg-slate-800/60 flex items-center justify-between gap-3">
                        <span className="text-sm truncate">{b.name}</span>
                        <span className="text-[11px] text-slate-500 shrink-0">{b.question_count ?? '—'} q</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

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

            {/* Recipient email chips */}
            <div className="md:col-span-2">
              <label className={label}>Notify recipients (internal users, by email)</label>
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-800 border border-slate-700 px-2 py-2">
                {recipients.map((em) => (
                  <span key={em} className="inline-flex items-center gap-1 rounded-md bg-emerald-600/20 text-emerald-300 text-xs px-2 py-1">
                    {em}
                    <button type="button" onClick={() => setRecipients((prev) => prev.filter((x) => x !== em))} className="text-emerald-400 hover:text-white">×</button>
                  </span>
                ))}
                <input
                  className="flex-1 min-w-[160px] bg-transparent text-sm px-1 py-1 focus:outline-none"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  onKeyDown={onEmailKey}
                  onBlur={() => emailInput.trim() && addEmail(emailInput)}
                  placeholder={recipients.length ? 'Add another…' : 'name@company.com  (Enter to add)'}
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">On publish, each recipient gets an email with a direct exam link + an in-app notification. Only matched internal users are notified.</p>
            </div>

            <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} className="accent-emerald-500" /> Publish immediately</label>
            <button disabled={creating} className="md:col-span-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2.5 font-bold disabled:opacity-50">{creating ? 'Creating…' : 'Create exam'}</button>
          </form>
        )}

        <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
          {loading ? <div className="p-4"><SkeletonList rows={4} avatar={false} /></div> : exams.length === 0 ? (
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

      {showBankWizard && (
        <BankCreationModal
          user={me}
          courses={courses}
          onClose={() => setShowBankWizard(false)}
          onCreated={async () => {
            setShowBankWizard(false);
            // Reload and auto-select the newest bank (highest id).
            try {
              const r = await ApiService.getBanks(undefined, 1, 200);
              const list = (r?.items || []) as Bank[];
              setBanks(list);
              if (list.length) {
                const newest = list.reduce((a, b) => (b.id > a.id ? b : a), list[0]);
                setBankId(newest.id);
              }
            } catch {
              await loadBanks();
            }
          }}
        />
      )}
    </div>
  );
}
