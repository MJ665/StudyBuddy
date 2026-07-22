import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'motion/react';
import ApiService from '../../services/ApiService';

interface HeatmapDay {
  date: string;
  count: number;
  weekday: number;
}

interface ActivityHeatmapProps {
  userId: number;
  initialData?: {
    heatmap: HeatmapDay[];
    total_active_days: number;
    max_day_count: number;
  };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun'];

function getColor(count: number, max: number): string {
  if (count === 0) return 'bg-slate-100/50 dark:bg-slate-800/40 border border-slate-200/10 dark:border-slate-700/20';
  const pct = max > 0 ? count / max : 0;
  
  if (pct < 0.25) return 'bg-indigo-400/30 dark:bg-indigo-900/40 border border-indigo-400/20';
  if (pct < 0.50) return 'bg-indigo-500 dark:bg-indigo-700 shadow-[inset_0_0_4px_rgba(0,0,0,0.1)]';
  if (pct < 0.75) return 'bg-violet-500 dark:bg-violet-600';
  return 'bg-fuchsia-600 dark:bg-fuchsia-500 shadow-[0_0_10px_rgba(192,38,211,0.3)] ring-1 ring-fuchsia-400/30';
}

export default function ActivityHeatmap({ userId, initialData }: ActivityHeatmapProps) {
  const [data, setData] = useState<HeatmapDay[]>(initialData?.heatmap || []);
  const [maxCount, setMaxCount] = useState(initialData?.max_day_count || 1);
  const [totalActive, setTotalActive] = useState(initialData?.total_active_days || 0);
  const [loading, setLoading] = useState(!initialData);
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);

  const fetchData = useCallback(() => {
    if (initialData) return;
    setLoading(true);
    ApiService.getUserActivityHeatmap(userId)
      .then((res: any) => {
        setData(res.heatmap || []);
        setMaxCount(res.max_day_count || 1);
        setTotalActive(res.total_active_days || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [userId, initialData]);

  useEffect(() => {
    if (!initialData) {
      fetchData();
    } else {
      setData(initialData.heatmap);
      setMaxCount(initialData.max_day_count);
      setTotalActive(initialData.total_active_days);
      setLoading(false);
    }
  }, [userId, initialData, fetchData]);

  // Real-Time Sync via SSE (Only if not provided initialData or if it's the current user)
  useEffect(() => {
    const token = localStorage.getItem('study_token');
    if (!token || initialData) return;

    const apiBase = process.env.NEXT_PUBLIC_API_BASE || '/api';
    const sseUrl = `${apiBase}/auth/notifications/stream?token=${token}`;
    
    const eventSource = new EventSource(sseUrl);
    let lastActivityTs: string | null = null;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.activity_ts && data.activity_ts !== lastActivityTs) {
          if (lastActivityTs !== null) {
            fetchData();
          }
          lastActivityTs = data.activity_ts;
        }
      } catch (err) {
        console.error("Heatmap SSE Error:", err);
      }
    };

    return () => eventSource.close();
  }, [userId, fetchData, initialData]);

  if (loading) {
    return (
      <div className="w-full h-24 flex items-center justify-center">
        <div className="animate-pulse text-slate-400 text-sm">Loading activity...</div>
      </div>
    );
  }

  const firstDayOfWeek = data[0]?.weekday ?? 0;
  const paddedDays: (HeatmapDay | null)[] = [
    ...Array(firstDayOfWeek).fill(null),
    ...data,
  ];

  const weeks: (HeatmapDay | null)[][] = [];
  for (let i = 0; i < paddedDays.length; i += 7) {
    weeks.push(paddedDays.slice(i, i + 7));
  }

  const monthLabels: { week: number; label: string }[] = [];
  let lastMonth = -1;
  weeks.forEach((week, wi) => {
    const firstNonNull = week.find((d) => d !== null);
    if (firstNonNull) {
      const m = new Date(firstNonNull.date).getMonth();
      if (m !== lastMonth) {
        monthLabels.push({ week: wi, label: MONTHS[m] });
        lastMonth = m;
      }
    }
  });

  return (
    <div className="relative select-none">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{totalActive} active days in the last year</span>
        <div className="flex items-center gap-1 text-[10px] font-black uppercase tracking-widest text-slate-500">
          <span>Less</span>
          {[0, 0.1, 0.4, 0.7, 1].map((pct, i) => (
            <div
              key={i}
              className={`h-3 w-3 rounded-sm ${pct === 0 ? 'bg-white/5' : pct < 0.2 ? 'bg-indigo-900/60' : pct < 0.4 ? 'bg-indigo-700' : pct < 0.7 ? 'bg-indigo-500' : 'bg-indigo-400'}`}
            />
          ))}
          <span>More</span>
        </div>
      </div>

      <div className="flex ml-7 mb-1 overflow-hidden">
        {weeks.map((_, wi) => {
          const label = monthLabels.find((ml) => ml.week === wi);
          return (
            <div key={wi} className="flex-1 min-w-0">
              {label ? (
                <span className="text-[9px] font-black text-slate-600 uppercase whitespace-nowrap">{label.label}</span>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="flex gap-0.5">
        <div className="flex flex-col gap-0.5 mr-1">
          {DAYS.map((d, i) => (
            <div key={i} className="h-3 text-[9px] font-black text-slate-600 leading-3 w-6 text-right pr-1">
              {d}
            </div>
          ))}
        </div>

        <div className="flex gap-0.5 flex-1 overflow-x-auto pb-2 scrollbar-hide">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5 shrink-0">
              {Array(7).fill(null).map((_, di) => {
                const day = week[di] ?? null;
                return (
                  <motion.div
                    key={di}
                    className={`h-3 w-3 rounded-sm cursor-pointer transition-all duration-150 ${day ? getColor(day.count, maxCount) : 'bg-transparent'}`}
                    whileHover={{ scale: 1.5, zIndex: 10 }}
                    onMouseEnter={(e) => {
                      if (!day) return;
                      const rect = (e.target as HTMLElement).getBoundingClientRect();
                      setTooltip({
                        text: `${day.date}: ${day.count} activities`,
                        x: rect.left,
                        y: rect.top - 30,
                      });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {tooltip && (
        <div
          className="fixed z-50 px-3 py-1.5 bg-slate-800 border border-white/10 text-white text-[10px] font-black rounded-lg shadow-2xl pointer-events-none whitespace-nowrap uppercase tracking-widest"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
