import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  LineChart, Line, AreaChart, Area, Cell, ScatterChart, Scatter, ZAxis,
  PieChart, Pie
} from 'recharts';
import { motion } from 'motion/react';
import ApiService from '../../services/ApiService';

interface ComparisonChartProps {
  data: any[];
  type: 'bar' | 'line' | 'area';
  dataKey: string;
  nameKey: string;
  color?: string;
}

export function ComparisonChart({ data, type, dataKey, nameKey, color = "#6366f1" }: ComparisonChartProps) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return (
      <div className="h-64 w-full bg-slate-900 border border-white/5 rounded-3xl animate-pulse" />
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center bg-slate-900/50 rounded-3xl border border-white/5 italic text-slate-500 text-xs">
        Insufficient data for visualization
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900 border border-white/10 p-3 rounded-xl shadow-2xl">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">{label}</p>
          <p className="text-sm font-black text-white">{payload[0].value}% Accuracy</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-64 w-full min-h-[256px] min-w-[300px]">
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
        {type === 'bar' ? (
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis 
              dataKey={nameKey} 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: '#64748b', fontSize: 10, fontWeight: 700 }}
              dy={10}
            />
            <YAxis 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: '#64748b', fontSize: 10, fontWeight: 700 }}
              domain={[0, 100]}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar dataKey={dataKey} radius={[4, 4, 0, 0]} barSize={40}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry[dataKey] > 80 ? '#10b981' : entry[dataKey] > 60 ? '#6366f1' : '#f43f5e'} />
              ))}
            </Bar>
          </BarChart>
        ) : type === 'line' ? (
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey={nameKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} domain={[0, 100]} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={3} dot={{ r: 4, fill: color, strokeWidth: 2, stroke: '#0f172a' }} />
          </LineChart>
        ) : (
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey={nameKey} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} domain={[0, 100]} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey={dataKey} stroke={color} fillOpacity={1} fill="url(#colorValue)" strokeWidth={3} />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export function HealthOverviewChart({ groupData, cohortData }: { groupData: any[], cohortData?: any[] }) {
    const [view, setView] = useState<'Group' | 'Cohort'>('Group');
    const data = view === 'Group' ? groupData : (cohortData || groupData);

    return (
        <div className="space-y-4">
            {cohortData && (
                <div className="flex bg-slate-800 p-1 rounded-xl w-max mb-4">
                    <button onClick={() => setView('Group')} className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${view === 'Group' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}>Group Health</button>
                    <button onClick={() => setView('Cohort')} className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${view === 'Cohort' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}>Cohort Health</button>
                </div>
            )}
            {data.map((item, idx) => (
                <div key={idx} className="space-y-1.5">
                    <div className="flex justify-between items-end">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{item.chapter}</span>
                        <span className="text-xs font-black text-white">{item.accuracy}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${item.accuracy}%` }}
                            className={`h-full rounded-full ${item.accuracy > 80 ? 'bg-emerald-500' : item.accuracy > 60 ? 'bg-indigo-500' : 'bg-rose-500'}`}
                        />
                    </div>
                </div>
            ))}
        </div>
    );
}

// ─── Scientific Analytics Charts (Section 12) ─────────────────────────────────

/** Method #4 — Engagement Decay Index */
export function EngagementDecayWidget({ batchId }: { batchId?: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ApiService.getEngagementDecay(batchId).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [batchId]);

  if (loading) return <div className="h-24 animate-pulse bg-slate-800 rounded-2xl" />;
  if (!data) return null;

  const isPositive = data.decay_index_pct >= 0;

  return (
    <div className={`p-5 rounded-2xl border ${isPositive ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-rose-500/5 border-rose-500/20'}`}>
      <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-2">Engagement Decay Index</p>
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-2xl font-black ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isPositive ? '+' : ''}{data.decay_index_pct}%
          </p>
          <p className="text-[10px] text-slate-400 mt-1">{data.risk_level}</p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <p>{data.recent_7d_active} active (7d)</p>
          <p>vs {data.historical_weekly_avg} avg</p>
        </div>
      </div>
      <p className="text-[10px] text-slate-500 mt-3">{data.interpretation}</p>
    </div>
  );
}

/** Method #30 — Composite Health Index gauge */
export function CompositeHealthGauge({ batchId }: { batchId?: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ApiService.getCompositeHealthIndex(batchId).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [batchId]);

  if (loading) return <div className="h-32 animate-pulse bg-slate-800 rounded-2xl" />;
  if (!data) return null;

  const gradeColor = data.grade === 'A' ? '#10b981' : data.grade === 'B' ? '#6366f1' : data.grade === 'C' ? '#f59e0b' : '#f43f5e';
  const gaugeData = [
    { name: 'CHI', value: data.chi, fill: gradeColor },
    { name: 'Remaining', value: 100 - data.chi, fill: '#1e293b' }
  ];

  return (
    <div className="p-5 rounded-2xl border border-surface-bright bg-surface-dim">
      <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-4">Composite Health Index (CHI)</p>
      <div className="flex items-center gap-6">
        <div className="relative w-24 h-24">
          <ResponsiveContainer width={96} height={96}>
            <PieChart>
              <Pie data={gaugeData} cx="50%" cy="50%" innerRadius={28} outerRadius={40} startAngle={90} endAngle={-270} dataKey="value" strokeWidth={0} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-black" style={{ color: gradeColor }}>{data.grade}</span>
          </div>
        </div>
        <div>
          <p className="text-3xl font-black text-white">{data.chi}<span className="text-sm text-slate-500">/100</span></p>
          <div className="mt-2 space-y-1 text-[10px] text-slate-400">
            <p>Accuracy: {data.components?.avg_accuracy_pct}%</p>
            <p>Participation: {data.components?.participation_rate_pct}%</p>
            <p>Volume Score: {data.components?.attempt_volume_score}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Method #1 — Learning Velocity Curve */
export function LearningVelocityChart({ userId }: { userId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    ApiService.getLearningVelocity(userId).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <div className="h-40 animate-pulse bg-slate-800 rounded-2xl" />;
  if (!data || !data.trend?.length) return (
    <div className="h-40 flex items-center justify-center text-slate-500 text-xs">Insufficient attempt history</div>
  );

  const isPositive = data.slope > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Learning Velocity (slope)</p>
        <span className={`text-xs font-black ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
          {isPositive ? '↑' : '↓'} {Math.abs(data.slope)}/attempt — {data.interpretation}
        </span>
      </div>
      <div className="h-40 w-full min-h-[160px]">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data.trend} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="attempt" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 9 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 9 }} domain={[0, 100]} />
            <Tooltip formatter={(val: any) => [`${val}%`, 'Accuracy']} contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
            <Line type="monotone" dataKey="accuracy" stroke={isPositive ? '#10b981' : '#f43f5e'} strokeWidth={2} dot={{ r: 3, fill: isPositive ? '#10b981' : '#f43f5e' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Method #11 — Performance Distribution (Z-Score scatter map) */
export function PerformanceDistributionChart({ batchId, groupId }: { batchId?: number; groupId?: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ApiService.getPerformanceDistribution({ batch_id: batchId, group_id: groupId })
      .then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [batchId, groupId]);

  if (loading) return <div className="h-64 animate-pulse bg-slate-800 rounded-2xl" />;
  if (!data?.distribution?.length) return (
    <div className="h-64 flex items-center justify-center text-slate-500 text-xs bg-slate-900/40 rounded-2xl border border-slate-800">
      No distribution data
    </div>
  );

  const quadrantColor: Record<string, string> = {
    'Star': '#10b981', 'Solid Performer': '#6366f1', 'Rising Star': '#f59e0b', 'At-Risk': '#f43f5e'
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Performance Distribution (Z-Score)</p>
        <p className="text-[10px] text-slate-400">μ={data.mean}% σ={data.std_dev} · N={data.cohort_size}</p>
      </div>
      <div className="flex gap-3 flex-wrap">
        {Object.entries(quadrantColor).map(([q, c]) => (
          <div key={q} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: c }} />
            <span className="text-[9px] text-slate-400 font-bold">{q}</span>
          </div>
        ))}
      </div>
      <div className="h-48 min-h-[192px]">
        <ResponsiveContainer width="100%" height={192}>
          <ScatterChart margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis type="number" dataKey="x" name="Avg Score" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 9 }} />
            <YAxis type="number" dataKey="y" name="Z-Score" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 9 }} />
            <ZAxis range={[40, 40]} />
            <Tooltip content={({ payload }) => {
              if (!payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-slate-900 border border-white/10 p-2 rounded-xl text-xs">
                  <p className="font-black text-white">{d.full_name}</p>
                  <p className="text-slate-400">{d.quadrant} · {d.avg_score}% · z={d.z_score}</p>
                </div>
              );
            }} />
            {(data.distribution || []).map((entry: any, i: number) => (
              <Scatter key={i} data={[{ x: entry.avg_score, y: entry.z_score, ...entry }]} fill={quadrantColor[entry.quadrant] || '#6366f1'} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
/** Method #10 — Strategic Leaderboard (Enhanced Multi-Metric Competitive Map) */
export function LeaderboardTable({ groupId, onIntel }: { groupId: number; onIntel?: (slug: string | number) => void }) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<string>('overall_score');

  useEffect(() => {
    if (!groupId) return;
    ApiService.getGroupLeaderboard(groupId)
      .then(setData)
      .catch((err) => console.error("Leaderboard fail:", err))
      .finally(() => setLoading(false));
  }, [groupId]);

  if (loading) return <div className="h-64 animate-pulse bg-slate-800 rounded-3xl" />;
  if (!data?.length) return (
    <div className="h-64 flex items-center justify-center text-slate-500 text-xs bg-slate-900/40 rounded-3xl border border-white/5 italic">
      No performance vectors detected in this sector
    </div>
  );

  const sorted = [...data].sort((a: any, b: any) => (b[sortBy] || 0) - (a[sortBy] || 0));
  const cols = [
    { key: 'overall_score', label: 'Score' },
    { key: 'quiz_accuracy', label: 'Quiz' },
    { key: 'coding_accuracy', label: 'Code' },
    { key: 'ai_avg_score', label: 'AI Score' },
    { key: 'assignment_completion', label: 'Tasks' },
    { key: 'streak', label: 'Streak' },
  ];

  const riskColor = (r: string) =>
    r === 'On Track' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' :
    r === 'Medium Risk' ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' :
    'text-rose-400 bg-rose-500/10 border-rose-500/20';

  return (
    <div className="space-y-3">
      {/* Sort pills */}
      <div className="flex gap-2 flex-wrap">
        {cols.map(c => (
          <button
            key={c.key}
            onClick={() => setSortBy(c.key)}
            className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
              sortBy === c.key ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-500 hover:text-white'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5">
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500">#</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500">Learner</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Quiz</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Code</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">AI Score</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Tasks</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">🔥</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Days</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Trend</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-center">Risk</th>
              <th className="pb-3 text-[9px] font-black uppercase tracking-widest text-slate-500 text-right">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sorted.map((user, idx) => {
              const isTop3 = idx < 3;
              const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : null;
              return (
                <tr
                  key={idx}
                  className="group hover:bg-white/[0.02] transition-colors cursor-pointer"
                  onClick={() => onIntel?.(user.custom_slug || (user.email ? user.email.split('@')[0] : user.user_id))}
                >
                  <td className="py-3 pr-2">
                    <span className={`text-sm ${isTop3 ? '' : 'text-slate-500 text-xs font-bold'}`}>
                      {medal || `#${idx + 1}`}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-[9px] font-black text-indigo-400 shrink-0">
                        {user.profile_photo_url ? (
                          <img src={user.profile_photo_url} className="w-full h-full rounded-lg object-cover" alt="" />
                        ) : user.full_name?.charAt(0)}
                      </div>
                      <div>
                        <p className="text-xs font-black text-white max-w-[100px] truncate">{user.full_name}</p>
                        <p className="text-[9px] text-slate-600">{user.total_quiz_attempts}q {user.total_coding_attempts}c</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[10px] font-bold ${user.quiz_accuracy > 80 ? 'text-emerald-400' : user.quiz_accuracy > 60 ? 'text-indigo-400' : 'text-rose-400'}`}>
                      {user.quiz_accuracy}%
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[10px] font-bold ${user.coding_accuracy > 70 ? 'text-emerald-400' : user.coding_accuracy > 50 ? 'text-indigo-400' : 'text-slate-500'}`}>
                      {user.coding_accuracy}%
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[10px] font-bold ${user.ai_avg_score > 75 ? 'text-purple-400' : user.ai_avg_score > 50 ? 'text-indigo-400' : 'text-slate-500'}`}>
                      {user.ai_avg_score > 0 ? `${user.ai_avg_score}%` : '—'}
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[10px] font-bold ${user.assignment_completion >= 80 ? 'text-emerald-400' : user.assignment_completion >= 50 ? 'text-amber-400' : 'text-slate-500'}`}>
                      {user.assignment_completion}%
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className="text-[10px] text-orange-400 font-bold">
                      {user.streak > 0 ? `${user.streak}d` : '—'}
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className="text-[10px] text-slate-400">{user.days_active}</span>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[10px] font-bold ${user.velocity > 5 ? 'text-emerald-400' : user.velocity < -5 ? 'text-rose-400' : 'text-slate-500'}`}>
                      {user.velocity > 5 ? '↑' : user.velocity < -5 ? '↓' : '→'}
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${riskColor(user.risk_level)}`}>
                      {user.risk_level === 'On Track' ? '✓' : user.risk_level === 'Medium Risk' ? '!' : '⚠'}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <div className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/5 border border-white/10">
                      <span className={`text-xs font-black ${user.overall_score >= 80 ? 'text-emerald-400' : user.overall_score >= 60 ? 'text-indigo-400' : 'text-white'}`}>
                        {user.overall_score}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
