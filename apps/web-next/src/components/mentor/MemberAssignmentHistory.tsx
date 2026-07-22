import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  ChevronLeft, 
  Calendar, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  FileText,
  Search,
  Filter,
  Loader2,
  TrendingUp,
  Brain,
  ClipboardList
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface AssignmentHistoryProps {
  student: any;
  onBack: () => void;
}

export default function MemberAssignmentHistory({ student, onBack }: AssignmentHistoryProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [attempts, setAttempts] = useState<any[]>([]);
  const [intel, setIntel] = useState<any>(null);
  const [filter, setFilter] = useState<'all' | 'quiz' | 'coding'>('all');

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const [historyRes, intelRes] = await Promise.all([
          ApiService.getUserAssignmentHistory(student.id),
          ApiService.getUserIntel(student.id)
        ]);
        setAttempts(historyRes);
        setIntel(intelRes);
      } catch (err: any) {
        toast('error', `Failed to load history: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [student.id]);

  const filteredAttempts = attempts.filter(a => filter === 'all' || a.type === filter);

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="h-full flex flex-col"
    >
      <header className="mb-10 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <button 
            onClick={onBack}
            className="p-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-2xl transition-all border border-slate-700 active:scale-95"
          >
            <ChevronLeft size={20} />
          </button>
          <div>
            <div className="flex items-center gap-2 text-indigo-400 mb-1">
              <Calendar size={16} />
              <span className="font-black uppercase tracking-[0.2em] text-[10px]">Academic Portfolio</span>
            </div>
            <h1 className="text-3xl font-black text-white">{student.full_name} <span className="text-slate-500 text-lg font-medium ml-2">— Assignment History</span></h1>
          </div>
        </div>

        <div className="flex gap-2 p-1 bg-surface-container rounded-2xl border border-surface-bright">
          {(['all', 'quiz', 'coding'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                filter === t ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </header>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-4">
          <Loader2 size={40} className="text-indigo-500 animate-spin" />
          <p className="text-slate-500 font-black uppercase tracking-widest text-xs">Reconstructing History...</p>
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 overflow-hidden">
          {/* Timeline View */}
          <div className="lg:col-span-2 overflow-y-auto pr-4 custom-scrollbar space-y-4">
            {filteredAttempts.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-20 bg-slate-900/40 rounded-[3rem] border border-dashed border-slate-800">
                <div className="w-20 h-20 bg-slate-800 rounded-3xl flex items-center justify-center text-slate-600 mb-6">
                  <ClipboardList size={40} />
                </div>
                <h3 className="text-xl font-black text-white mb-2">No Records Found</h3>
                <p className="text-slate-500 max-w-xs text-center text-sm leading-relaxed">
                  This academic portfolio is currently pristine. No attempts have been synchronized for the selected category.
                </p>
              </div>
            ) : (
              filteredAttempts.map((attempt) => (
                <div key={attempt.id} className="bg-surface-container p-6 rounded-[2.5rem] border border-surface-bright group hover:border-indigo-500/30 transition-all flex items-center justify-between">
                  <div className="flex items-center gap-6">
                    <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
                      attempt.is_correct || attempt.score >= 70 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'
                    }`}>
                      {attempt.type === 'coding' ? <Brain size={28} /> : <FileText size={28} />}
                    </div>
                    <div>
                      <h3 className="font-bold text-white text-lg">{attempt.assignment_title || attempt.bank_name}</h3>
                      <div className="flex items-center gap-4 mt-1 text-[10px] font-black uppercase tracking-widest text-slate-500">
                        <span className="flex items-center gap-1"><Calendar size={12} /> {new Date(attempt.attempted_at).toLocaleDateString()}</span>
                        <span className="flex items-center gap-1"><Clock size={12} /> {Math.floor(attempt.time_taken / 60)}m {attempt.time_taken % 60}s</span>
                        <span className={`px-2 py-0.5 rounded ${attempt.type === 'coding' ? 'bg-indigo-500/10 text-indigo-400' : 'bg-amber-500/10 text-amber-400'}`}>
                          {attempt.type}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="flex items-center justify-end gap-2 mb-1">
                      <p className="text-2xl font-black text-white">{attempt.score}<span className="text-slate-600 text-sm">/{attempt.total}</span></p>
                      {attempt.score >= 70 ? <CheckCircle2 className="text-emerald-500" size={20} /> : <AlertCircle className="text-amber-500" size={20} />}
                    </div>
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Accuracy Profile</p>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Aggregate Insights Sidebar */}
          <div className="space-y-6">
            <div className="bg-indigo-600 p-8 rounded-[3rem] text-white shadow-xl shadow-indigo-600/20 relative overflow-hidden group">
              <div className="absolute -top-10 -right-10 w-40 h-40 bg-white/10 blur-3xl rounded-full" />
              <TrendingUp className="mb-4 text-indigo-200" size={32} />
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-indigo-200 mb-2">Long-term Trajectory</p>
              <h3 className="text-3xl font-black mb-4">{intel?.metrics?.m17b_velocity_label?.value || 'Steady Growth'}</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-indigo-200">Avg. Accuracy</span>
                  <span className="font-bold">{intel?.metrics?.m02_overall_accuracy?.value || '0%'}</span>
                </div>
                <div className="w-full h-1.5 bg-indigo-900 rounded-full overflow-hidden">
                  <div className="h-full bg-white rounded-full" style={{ width: `${intel?.raw_vectors?.m02_overall_accuracy || 0}%` }} />
                </div>
              </div>
            </div>

            <div className="bg-surface-container p-8 rounded-[3rem] border border-surface-bright">
              <h4 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-6">Pedagogical Markers</h4>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0">
                    <CheckCircle2 size={20} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white mb-1">Concept Mastery</p>
                    <p className="text-[10px] text-slate-500 leading-relaxed">
                      {intel?.charts?.best_topic ? `Peak performance identified in ${intel.charts.best_topic.topic} with ${intel.charts.best_topic.avg_accuracy}% accuracy.` : 'Building core competencies across all domains.'}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
                    <AlertCircle size={20} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white mb-1">Attention Required</p>
                    <p className="text-[10px] text-slate-500 leading-relaxed">
                      {intel?.charts?.worst_topic ? `${intel.charts.worst_topic.topic} remains a recurring bottleneck with ${intel.charts.worst_topic.avg_accuracy}% average.` : 'No critical knowledge gaps detected in recent cycles.'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
