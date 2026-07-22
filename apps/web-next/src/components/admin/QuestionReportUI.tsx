import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Search, 
  Filter, 
  ExternalLink,
  MessageSquare,
  Clock,
  User,
  MoreVertical,
  Edit3,
  Trash2,
  Loader2
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

export default function QuestionReportUI() {
  const { toast } = useToast();
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'resolved'>('pending');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const res = await ApiService.getQuestionReports();
      setReports(res);
    } catch (err: any) {
      toast('error', `Failed to load reports: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (reportId: number, status: string) => {
    try {
      await ApiService.resolveQuestionReport(reportId);
      toast('success', `Report marked as ${status}`);
      fetchReports();
    } catch (err: any) {
      toast('error', `Action failed: ${err.message}`);
    }
  };

  const filteredReports = reports.filter(r => {
    const matchesFilter = filter === 'all' || r.status === filter;
    const matchesSearch = r.question_text?.toLowerCase().includes(searchQuery.toLowerCase()) || 
                         r.reason?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950/50 rounded-[3rem] border border-white/5 overflow-hidden">
      <header className="p-8 border-b border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 text-rose-400 mb-2">
            <AlertTriangle size={18} />
            <span className="font-black uppercase tracking-[0.2em] text-[10px]">Data Integrity Audit</span>
          </div>
          <h2 className="text-2xl font-black text-white">Question Reports</h2>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
            <input 
              type="text" 
              placeholder="Search reports..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="bg-slate-900 border border-white/10 rounded-2xl pl-12 pr-6 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-rose-500/50 transition-all w-64"
            />
          </div>

          <div className="flex p-1 bg-slate-900 rounded-xl border border-white/5">
            {(['all', 'pending', 'resolved'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
                  filter === f ? 'bg-white/10 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
        {loading ? (
          <div className="h-full flex flex-col items-center justify-center space-y-4">
            <Loader2 className="animate-spin text-rose-500" size={40} />
            <p className="text-slate-500 font-black uppercase tracking-widest text-xs">Scanning Report Cluster...</p>
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center space-y-6 opacity-50">
            <div className="w-20 h-20 rounded-full bg-slate-900 flex items-center justify-center text-slate-700 border border-white/5">
              <CheckCircle2 size={40} />
            </div>
            <p className="text-slate-500 font-bold">No items match your current filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {filteredReports.map(report => (
              <motion.div 
                key={report.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-slate-900/50 border border-white/5 rounded-3xl p-6 hover:border-rose-500/20 transition-all group"
              >
                <div className="flex justify-between items-start mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-slate-500">
                      <User size={20} />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{report.reporter_name || 'Anonymous User'}</p>
                      <div className="flex items-center gap-2 text-[10px] text-slate-500 font-black uppercase tracking-widest">
                        <Clock size={10} /> {new Date(report.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest ${
                    report.status === 'pending' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  }`}>
                    {report.status}
                  </span>
                </div>

                <div className="bg-slate-950/50 rounded-2xl p-5 mb-6 border border-white/5">
                  <p className="text-[10px] font-black text-rose-500 uppercase tracking-widest mb-2">Reported Content</p>
                  <p className="text-sm text-slate-300 font-medium leading-relaxed italic mb-4">"{report.question_text}"</p>
                  
                  <div className="flex gap-4 p-4 bg-rose-500/5 rounded-xl border border-rose-500/10">
                    <AlertTriangle size={16} className="text-rose-500 shrink-0" />
                    <div>
                      <p className="text-xs font-black text-rose-400 uppercase tracking-widest mb-1">Issue Logic</p>
                      <p className="text-xs text-slate-400">{report.reason}</p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-4">
                  <button className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-slate-500 hover:text-white transition-all">
                    <ExternalLink size={14} /> View Source Question
                  </button>
                  
                  {report.status === 'pending' && (
                    <div className="flex gap-2">
                      <button 
                        onClick={() => handleResolve(report.id, 'dismissed')}
                        className="px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border border-white/5"
                      >
                        Dismiss
                      </button>
                      <button 
                        onClick={() => handleResolve(report.id, 'resolved')}
                        className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest shadow-lg shadow-emerald-600/20 hover:scale-105 active:scale-95 transition-all"
                      >
                        Mark Resolved
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
