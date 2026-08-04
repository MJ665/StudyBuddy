'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ApiService from '@/services/ApiService';

interface Attempt {
  id: number;
  user_id: number;
  user_name?: string | null;
  user_email?: string | null;
  status: string;
  score: number | null;
  total: number | null;
  passed: boolean | null;
  flags: number;
  submitted_at: string | null;
}

interface ExamStats {
  title: string;
  participation: { invited: number; attempted: number; in_progress: number; completion_rate: number };
  scores: { pass_rate: number; average: number; median: number; highest: number; lowest: number; distribution: { range: string; count: number }[] };
  timing: { average_minutes: number; duration_minutes: number };
  questions: { question_id: number; question: string; answered: number; correct: number; correct_pct: number | null; manual_graded?: boolean }[];
  proctoring: { candidates_flagged: number; total_flags: number; avg_flags_per_candidate: number };
}

interface ProctorSnapshot { id: number; media_url: string; at: string | null; }
interface ProctorFlag { id: number; event_type: string; detail: string | null; at: string | null; }
interface ProctorVideo { id: number; media_url: string; at: string | null; }

function ProctorDetail({ attemptId }: { attemptId: number }) {
  const [data, setData] = useState<{ snapshots: ProctorSnapshot[]; flags: ProctorFlag[]; videos: ProctorVideo[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [vIdx, setVIdx] = useState(0);
  useEffect(() => {
    ApiService.getProctorEvents(attemptId)
      .then((r) => setData({ snapshots: r.snapshots || [], flags: r.flags || [], videos: r.video_chunks || [] }))
      .catch(() => setData({ snapshots: [], flags: [], videos: [] }))
      .finally(() => setLoading(false));
  }, [attemptId]);

  if (loading) return <div className="px-4 py-3 text-slate-500 text-xs">Loading proctor data…</div>;
  if (!data) return null;
  const fmt = (s: string | null) => (s ? new Date(s).toLocaleTimeString() : '—');
  return (
    <div className="px-4 py-4 bg-slate-950/60 border-b border-slate-800/50 space-y-4">
      {data.videos.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">Webcam recording ({data.videos.length} segment{data.videos.length > 1 ? 's' : ''})</div>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video
            key={data.videos[vIdx]?.id}
            src={data.videos[vIdx]?.media_url}
            controls
            autoPlay
            onEnded={() => setVIdx((i) => (i + 1 < data.videos.length ? i + 1 : i))}
            className="w-full max-w-md rounded-lg border border-slate-700 bg-black"
          />
          <div className="flex gap-1 mt-2 flex-wrap">
            {data.videos.map((v, i) => (
              <button key={v.id} onClick={() => setVIdx(i)}
                className={`text-[10px] px-2 py-1 rounded ${i === vIdx ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
                {fmt(v.at)}
              </button>
            ))}
          </div>
        </div>
      )}
      <div>
        <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">Webcam snapshots ({data.snapshots.length})</div>
        {data.snapshots.length === 0 ? (
          <div className="text-slate-600 text-xs">No snapshots captured.</div>
        ) : (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {data.snapshots.map((s) => (
              <a key={s.id} href={s.media_url} target="_blank" rel="noopener" className="flex-shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.media_url} alt={`snapshot ${fmt(s.at)}`} title={fmt(s.at)}
                  className="w-24 h-18 object-cover rounded-md border border-slate-700" />
              </a>
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">Flag timeline ({data.flags.length})</div>
        {data.flags.length === 0 ? (
          <div className="text-emerald-500/70 text-xs">No integrity flags.</div>
        ) : (
          <ul className="space-y-1">
            {data.flags.map((f) => (
              <li key={f.id} className="flex items-center gap-3 text-xs">
                <span className="text-slate-500 font-mono w-20">{fmt(f.at)}</span>
                <span className="text-amber-400 font-semibold">{f.event_type.replace(/_/g, ' ')}</span>
                {f.detail && <span className="text-slate-500 truncate">{f.detail}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function ProctorReviewPage() {
  const params = useParams();
  const examId = Number(Array.isArray(params.id) ? params.id[0] : params.id);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [stats, setStats] = useState<ExamStats | null>(null);

  useEffect(() => {
    ApiService.examAttemptsForReview(examId)
      .then((r) => setAttempts(r.attempts || []))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
    ApiService.examStats(examId).then((s) => setStats(s)).catch(() => setStats(null));
  }, [examId]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black">Proctor review</h1>
            <p className="text-slate-400 text-sm">Exam #{examId} · attempts &amp; integrity flags</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={async () => {
                try {
                  const blob = await ApiService.exportExamResults(examId);
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = `exam_${examId}_results.csv`; a.click();
                  URL.revokeObjectURL(url);
                } catch { setError('Export failed'); }
              }}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-bold"
            >
              Export CSV
            </button>
            <a href="/exams" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Exams</a>
          </div>
        </header>

        {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm mb-4">{error}</div>}

        {stats && (
          <section className="mb-6 space-y-4">
            {/* KPI tiles */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Attempted', value: `${stats.participation.attempted}/${stats.participation.invited || '—'}`, sub: `${stats.participation.completion_rate}% completion` },
                { label: 'Pass rate', value: `${stats.scores.pass_rate}%`, sub: `avg ${stats.scores.average}% · med ${stats.scores.median}%` },
                { label: 'Score range', value: `${stats.scores.lowest}–${stats.scores.highest}%`, sub: 'low – high' },
                { label: 'Avg time', value: `${stats.timing.average_minutes}m`, sub: `of ${stats.timing.duration_minutes}m` },
              ].map((k) => (
                <div key={k.label} className="rounded-xl bg-slate-900 border border-slate-800 p-4">
                  <div className="text-[10px] uppercase tracking-widest text-slate-500">{k.label}</div>
                  <div className="text-xl font-black mt-1">{k.value}</div>
                  <div className="text-[11px] text-slate-500">{k.sub}</div>
                </div>
              ))}
            </div>

            {/* Score distribution */}
            <div className="rounded-xl bg-slate-900 border border-slate-800 p-4">
              <div className="text-xs uppercase tracking-widest text-slate-500 mb-3">Score distribution</div>
              <div className="flex items-end gap-2 h-28">
                {stats.scores.distribution.map((b) => {
                  const max = Math.max(1, ...stats.scores.distribution.map((x) => x.count));
                  return (
                    <div key={b.range} className="flex-1 flex flex-col items-center justify-end gap-1">
                      <div className="w-full bg-emerald-600/70 rounded-t" style={{ height: `${(b.count / max) * 100}%` }} title={`${b.count}`} />
                      <div className="text-[10px] text-slate-500">{b.range}</div>
                      <div className="text-[10px] text-slate-400 font-bold">{b.count}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Question difficulty + proctoring summary */}
            <div className="grid md:grid-cols-2 gap-3">
              <div className="rounded-xl bg-slate-900 border border-slate-800 p-4">
                <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">Question difficulty (correct %)</div>
                <ul className="space-y-1.5 max-h-48 overflow-y-auto">
                  {stats.questions.map((q, i) => {
                    const pct = q.correct_pct;
                    const manual = q.manual_graded || pct === null;
                    return (
                      <li key={q.question_id} className="flex items-center gap-2 text-xs">
                        <span className="text-slate-500 w-6">Q{i + 1}</span>
                        <div className="flex-1 bg-slate-800 rounded h-2 overflow-hidden">
                          {!manual && <div className={`h-full ${(pct ?? 0) >= 60 ? 'bg-emerald-500' : (pct ?? 0) >= 30 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${pct ?? 0}%` }} />}
                        </div>
                        <span className="w-14 text-right text-slate-400">{manual ? 'manual' : `${pct}%`}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
              <div className="rounded-xl bg-slate-900 border border-slate-800 p-4">
                <div className="text-xs uppercase tracking-widest text-slate-500 mb-2">Proctoring integrity</div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-slate-400">Candidates flagged</span><span className="font-bold">{stats.proctoring.candidates_flagged}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Total flags</span><span className="font-bold">{stats.proctoring.total_flags}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Avg flags / candidate</span><span className="font-bold">{stats.proctoring.avg_flags_per_candidate}</span></div>
                </div>
              </div>
            </div>
          </section>
        )}

        <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-x-auto">
          <div className="min-w-[560px]">
          <div className="grid grid-cols-5 gap-2 px-4 py-3 text-xs uppercase tracking-widest text-slate-500 border-b border-slate-800">
            <span>User</span><span>Status</span><span>Score</span><span>Result</span><span>Flags</span>
          </div>
          {loading ? <div className="p-4 text-slate-500 text-sm">Loading…</div> : attempts.length === 0 ? (
            <div className="p-4 text-slate-500 text-sm">No attempts yet.</div>
          ) : attempts.map((a) => (
            <div key={a.id}>
              <button
                onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                className="w-full grid grid-cols-5 gap-2 px-4 py-2.5 border-b border-slate-800/50 text-sm items-center text-left hover:bg-slate-800/40 transition-colors"
              >
                <span className="min-w-0">
                  <span className="block truncate font-semibold">{a.user_name || `User ${a.user_id}`}</span>
                  {a.user_email && <span className="block truncate text-xs text-slate-500">{a.user_email}</span>}
                </span>
                <span className="text-slate-400">{a.status}</span>
                <span>{a.score != null ? `${a.score}/${a.total}` : '—'}</span>
                <span className={a.passed ? 'text-emerald-400' : a.passed === false ? 'text-rose-400' : 'text-slate-500'}>
                  {a.passed == null ? '—' : a.passed ? 'Pass' : 'Fail'}
                </span>
                <span className={a.flags > 0 ? 'text-amber-400 font-bold' : 'text-slate-500'}>
                  {a.flags > 0 ? `⚠ ${a.flags}` : '0'} <span className="text-slate-600">{expanded === a.id ? '▲' : '▼'}</span>
                </span>
              </button>
              {expanded === a.id && <ProctorDetail attemptId={a.id} />}
            </div>
          ))}
          </div>
        </div>
        <p className="text-center text-slate-600 text-xs mt-6">Powered by StudyBuddy</p>
      </div>
    </div>
  );
}
