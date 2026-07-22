import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, ChevronRight, TrendingUp, TrendingDown, Lightbulb, RefreshCw, Target } from 'lucide-react';
import ApiService from '../../services/ApiService';

interface TopicRec {
  topic: string;
  avg_accuracy: number;
  attempt_count: number;
}

interface NextTopicData {
  recommendation: string | null;
  reason: string;
  weak_topics: TopicRec[];
  strong_topics: TopicRec[];
}

export default function AINextTopicWidget({ groupId }: { groupId?: number }) {
  const [data, setData] = useState<NextTopicData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetch = async (showRefresh = false) => {
    if (!groupId) return;
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await ApiService.getAINextTopic(groupId);
      setData(res);
    } catch {
      // silent fail — don't break the dashboard
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetch(); }, [groupId]);

  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 animate-pulse">
        <div className="h-4 bg-slate-800 rounded w-1/3 mb-3" />
        <div className="h-3 bg-slate-800 rounded w-2/3" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-indigo-950/80 to-purple-950/80 border border-indigo-500/30 rounded-3xl p-6 relative overflow-hidden"
    >
      {/* Glow */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-500/20 rounded-xl flex items-center justify-center">
            <Sparkles size={16} className="text-indigo-400" />
          </div>
          <span className="text-xs font-black uppercase tracking-widest text-indigo-400">AI Recommendation</span>
        </div>
        <button
          onClick={() => fetch(true)}
          className="p-1.5 text-slate-500 hover:text-indigo-400 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {data.recommendation ? (
        <>
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 bg-indigo-500/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center shrink-0 mt-0.5">
              <Target size={18} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-white font-bold text-lg leading-tight">{data.recommendation}</p>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">{data.reason}</p>
            </div>
          </div>
        </>
      ) : (
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb size={20} className="text-amber-400 shrink-0" />
          <p className="text-slate-300 text-sm">{data.reason}</p>
        </div>
      )}

      {/* Topic Breakdown */}
      {(data.weak_topics.length > 0 || data.strong_topics.length > 0) && (
        <div className="mt-4 pt-4 border-t border-indigo-500/20 grid grid-cols-2 gap-3">
          {data.weak_topics.length > 0 && (
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-rose-400 mb-2 flex items-center gap-1">
                <TrendingDown size={10} /> Needs Work
              </p>
              {data.weak_topics.map(t => (
                <div key={t.topic} className="flex justify-between items-center mb-1">
                  <span className="text-xs text-slate-400 truncate max-w-[100px]">{t.topic}</span>
                  <span className="text-xs font-bold text-rose-400 shrink-0 ml-1">{t.avg_accuracy}%</span>
                </div>
              ))}
            </div>
          )}
          {data.strong_topics.length > 0 && (
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-emerald-400 mb-2 flex items-center gap-1">
                <TrendingUp size={10} /> Strong Areas
              </p>
              {data.strong_topics.map(t => (
                <div key={t.topic} className="flex justify-between items-center mb-1">
                  <span className="text-xs text-slate-400 truncate max-w-[100px]">{t.topic}</span>
                  <span className="text-xs font-bold text-emerald-400 shrink-0 ml-1">{t.avg_accuracy}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
