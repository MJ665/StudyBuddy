'use client';
/* Extracted verbatim from LDAdminDashboard.tsx (Phase 4 decomposition).
   eslint-disable-next-line — imports copied wholesale; unused ones are
   pruned in the Phase 6 lint pass. */
/* eslint-disable @typescript-eslint/no-unused-vars */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Users, Building2, TrendingUp, ShieldCheck, Search, Plus,
  ChevronRight, ChevronDown, Layers, Settings, X,
  Filter, UserPlus, Database, Terminal, Target, Upload,
  Check, Loader2, ArrowLeft, Trash2, Mail, BadgeCheck, Download,
  Clock, Sparkles, BookmarkPlus, ShieldAlert, RefreshCw, FileText, Brain, Activity, Shield, Trophy,
  Play, CheckCircle, AlertCircle, Calendar, AlertTriangle, Info
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';
import ApiService, { ExecutiveSummary, BatchInsights } from '../../services/ApiService';
import { useToast } from '../ui/Toast';
import AssignmentCreationModal from '../dashboard/AssignmentCreationModal';
import CourseEnrollmentModal from '../dashboard/CourseEnrollmentModal';
import CodingQuestionModal from '../dashboard/CodingQuestionModal';
import BankCreationModal from '../dashboard/BankCreationModal';
import NotificationCenter from '../common/NotificationCenter';
import { ComparisonChart, CompositeHealthGauge, EngagementDecayWidget, PerformanceDistributionChart, LeaderboardTable } from '../dashboard/AnalyticsCharts';
import UserIntelPanel from '../dashboard/UserIntelPanel';
import QuestionManagement from '../dashboard/QuestionManagement';
import QuestionReportUI from './QuestionReportUI';
import DataIntegrityDashboard from '../dashboard/DataIntegrityDashboard';
import SystemHealthMonitor from '../dashboard/SystemHealthMonitor';

export function ResourceModal({ type, initialName = '', onClose, onSubmit, mode = 'CREATE' }: any) {
  const [name, setName] = useState(initialName);
  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-[130] flex items-center justify-center p-6">
      <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="bg-slate-900 border border-white/10 p-10 rounded-[3rem] w-full max-w-sm shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-brand-primary to-indigo-600" />
        <h3 className="text-2xl font-black text-white mb-2">{mode === 'CREATE' ? 'Initialize' : 'Modify'} {type}</h3>
        <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-10">Strategic Structural Governance</p>

        <div className="space-y-1 mb-8">
          <label className="text-[9px] font-black uppercase tracking-widest text-slate-600 ml-2">Identifier</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={`Enter name...`}
            className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 text-white font-bold focus:ring-2 focus:ring-brand-primary/50 outline-none transition-all"
          />
        </div>

        <div className="flex gap-4">
          <button onClick={onClose} className="flex-1 py-4 font-black uppercase tracking-widest text-xs text-slate-500 hover:text-white transition-colors">Abort</button>
          <button
            onClick={() => onSubmit(name)}
            disabled={!name.trim() || name === initialName}
            className="flex-1 py-4 bg-brand-primary text-slate-950 rounded-2xl font-black uppercase tracking-widest text-xs shadow-lg shadow-brand-primary/20 hover:brightness-110 disabled:opacity-30 disabled:grayscale transition-all"
          >
            {mode === 'CREATE' ? 'Execute' : 'Update'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}


export function DeleteModal({ type, name, onClose, onConfirm, processing }: any) {
  return (
    <div className="fixed inset-0 bg-rose-950/20 backdrop-blur-xl z-[140] flex items-center justify-center p-6">
      <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="bg-slate-900 border border-rose-500/30 p-10 rounded-[3rem] w-full max-w-sm shadow-2xl relative overflow-hidden text-center">
        <div className="w-20 h-20 bg-rose-500/10 rounded-full flex items-center justify-center mx-auto mb-6 text-rose-500">
          <ShieldAlert size={40} />
        </div>
        <h3 className="text-2xl font-black text-white mb-2">Purge Request</h3>
        <p className="text-[10px] text-rose-400 font-black uppercase tracking-[0.2em] mb-6">Irreversible Registry Deletion</p>

        <div className="p-6 bg-rose-500/5 rounded-3xl border border-rose-500/10 mb-8">
          <p className="text-sm text-slate-300">Are you certain you want to purge <span className="text-white font-bold">{name}</span> ({type}) from the organizational hierarchy?</p>
          <p className="text-[10px] text-rose-500 font-black uppercase tracking-widest mt-4">All downstream dependencies will be lost.</p>
        </div>

        <div className="flex flex-col gap-3">
          <button
            disabled={processing}
            onClick={onConfirm}
            className="w-full py-5 bg-rose-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs shadow-xl shadow-rose-900/40 hover:bg-rose-500 transition-all flex items-center justify-center gap-3"
          >
            {processing ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
            Confirm Purge
          </button>
          <button onClick={onClose} disabled={processing} className="w-full py-4 font-black uppercase tracking-widest text-xs text-slate-500 hover:text-white transition-colors">Cancel Protocol</button>
        </div>
      </motion.div>
    </div>
  );
}


export function BulkAddModal({ onClose, onSubmit, tree, currentUser }: any) {
  const isGroupAdmin = currentUser?.role === 'GroupAdmin';
  const assignedGroupId = currentUser?.assigned_groups?.[0] || currentUser?.group_id;

  const [groupId, setGroupId] = useState(isGroupAdmin && assignedGroupId ? String(assignedGroupId) : '');
  const [csvText, setCsvText] = useState('');
  const groups: any[] = [];
  tree?.forEach((o: any) => {
    o.departments?.forEach((d: any) => {
      d.verticals?.forEach((v: any) => {
        v.batches?.forEach((b: any) => {
          b.groups?.forEach((g: any) => {
            groups.push({ id: g.id, name: `${o.name} > ${b.name} > ${g.name}` });
          });
        });
      });
    });
  });
  return (
    <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-xl z-[130] flex items-center justify-center p-6">
      <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="bg-slate-900 border border-white/10 p-10 rounded-[3.5rem] w-full max-w-2xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-indigo-500 shadow-[0_0_20px_rgba(99,102,241,0.5)]" />
        <h3 className="text-3xl font-black text-white mb-2">Bulk Onboarding Protocol</h3>
        <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mb-10">Cross-Organization Network Bridging</p>
        <div className="space-y-8">
          <div>
            <label className="block text-[10px] font-black uppercase text-slate-500 mb-2">Operational Node Target</label>
            {isGroupAdmin ? (
              <div className="w-full bg-slate-950/50 border border-indigo-500/30 rounded-2xl p-4 text-indigo-400 font-bold flex items-center gap-2">
                <Shield size={14} /> {groups.find(g => String(g.id) === String(groupId))?.name || 'Authorized Scoped Context'}
              </div>
            ) : (
              <select value={groupId} onChange={(e) => setGroupId(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none focus:ring-2 focus:ring-indigo-500/30 transition-all">
                <option value="">Select Target Sync Point...</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            )}
          </div>
          <div className="flex items-center p-4 bg-indigo-500/5 rounded-2xl border border-indigo-500/10">
            <p className="text-[10px] text-indigo-400 leading-relaxed font-bold">Each account receives individual credentials by email after onboarding.</p>
          </div>
          <div>
            <label className="block text-[10px] font-black uppercase text-slate-500 mb-2">Directory Registry (Format: Full Name, email@host.com)</label>
            <textarea value={csvText} onChange={(e) => setCsvText(e.target.value)} className="w-full h-48 bg-slate-950 border border-white/5 rounded-3xl p-6 text-white font-mono text-xs resize-none outline-none focus:ring-2 focus:ring-indigo-500/30 transition-all" placeholder="John Wick, baba.yaga@continental.com" />
          </div>
          <div className="flex gap-4">
            <button onClick={onClose} className="flex-1 py-5 font-black uppercase tracking-widest text-xs text-slate-500 hover:text-white transition-colors">Cancel Protocol</button>
            <button onClick={() => {
              const lines = csvText.split('\n').filter(l => l.includes(','));
              const users = lines.map(l => {
                const [n, e] = l.split(',').map(s => s.trim());
                return { full_name: n, email: e, role: 'Member' };
              });
              onSubmit(parseInt(groupId), users);
            }} disabled={!groupId || !csvText.trim()} className="flex-1 py-5 bg-indigo-600 text-white rounded-[2rem] font-black uppercase tracking-widest text-xs shadow-xl shadow-indigo-600/30 hover:bg-indigo-500 transition-all">Begin Synchronization</button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}


export function UserDetailsModal({ user, onClose }: { user: any; onClose: () => void }) {
  const { toast } = useToast();
  const [insights, setInsights] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInsights = async () => {
      try {
        const res = await ApiService.getUserInsights(user.id);
        console.log("Intel Sync Result:", res);
        setInsights(res);
      } catch (err) {
        console.error("Failed to fetch entity intel", err);
        toast('error', 'Intel Synchronization Failed: Neural link unstable.');
      } finally {
        setLoading(false);
      }
    };
    fetchInsights();
  }, [user.id]);

  const [generatingAtlas, setGeneratingAtlas] = useState(false);
  const handleGenerateAtlas = async () => {
    setGeneratingAtlas(true);
    try {
      const res = await ApiService.getMemberGrowthAtlas(user.id);
      console.log("Growth Atlas generated:", res);
      // We can show this in an alert or separate panel, for now toast success
      toast('success', 'AI Growth Atlas compiled! Summary injected into narrative.');
      // Refresh insights to show new narrative if backend updates it (or just rely on the toast for now)
      const fresh = await ApiService.getUserInsights(user.id);
      setInsights(fresh);
    } catch (err: any) {
      toast('error', 'Atlas generation failed — neural throughput limit reached.');
    } finally {
      setGeneratingAtlas(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-xl z-[150] flex items-center justify-center p-6 overflow-y-auto">
      <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="bg-surface-container border border-surface-bright p-10 rounded-[4rem] w-full max-w-2xl shadow-2xl relative my-auto">
        <div className="flex justify-between items-start mb-10">
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 rounded-[2.5rem] bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary text-4xl font-black shadow-lg shadow-brand-primary/5">{user.full_name?.[0] || 'U'}</div>
            <div>
              <h3 className="text-4xl font-black text-white mb-2">{user.full_name}</h3>
              <div className="flex gap-2">
                <span className="px-3 py-1 rounded-lg bg-indigo-500/10 text-indigo-400 text-[10px] font-black uppercase tracking-widest border border-indigo-500/20">Access: {user.role}</span>
                <span className="px-3 py-1 rounded-lg bg-white/5 text-slate-400 text-[10px] font-black uppercase tracking-widest border border-white/5">GID: #{user.group_id}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full text-slate-500 hover:text-white transition-all"><X size={28} /></button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="p-6 bg-slate-900/50 border border-slate-800 rounded-3xl group hover:border-brand-primary/30 transition-all">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2">Network Identity</p>
            <div className="flex items-center gap-2">
              <Mail size={12} className="text-brand-primary/60" />
              <p className="text-xs font-bold text-white truncate">{user.email}</p>
            </div>
          </div>
          <div className="p-6 bg-slate-900/50 border border-slate-800 rounded-3xl group hover:border-brand-primary/30 transition-all">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2">Pedagogical Sector</p>
            <div className="flex items-center gap-2">
              <Building2 size={12} className="text-brand-primary/60" />
              <p className="text-xs font-bold text-white truncate">{user.batch_name || user.vertical_name || 'Autonomous Registry'}</p>
            </div>
          </div>
        </div>

        <div className="mb-10">
          <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-brand-primary mb-6 flex items-center gap-2">
            <TrendingUp size={14} /> Comprehensive Sync Insights
          </h4>

          {loading ? (
            <div className="p-12 bg-slate-900/40 rounded-[2.5rem] border border-slate-800 flex flex-col items-center justify-center gap-4 border-dashed">
              <Loader2 className="animate-spin text-brand-primary" size={32} />
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Compiling Neural History...</p>
            </div>
          ) : insights ? (
            <div className="space-y-6">
              {/* Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { label: 'Sync Score', val: `${insights.metrics.synchronization.avg_accuracy}%`, color: 'indigo-400' },
                  { label: 'Group Avg Sync', val: `${insights.metrics.advanced.group_average_accuracy}%`, color: 'slate-400' },
                  { label: 'Weighted Prof.', val: `${insights.metrics.advanced.weighted_proficiency}%`, color: 'brand-primary' },
                  { label: 'Consistency', val: `${insights.metrics.advanced.consistency_score}%`, color: 'emerald-400' },
                  { label: 'Quiz Volume', val: insights.metrics.synchronization.volume, color: 'indigo-400' },
                  { label: 'Lab Success', val: `${insights.metrics.algorithmic_lab.success_rate}%`, color: 'emerald-400' },
                  { label: 'Sprint Streak', val: `${insights.metrics.advanced.streak} Days`, color: 'rose-400' }
                ].map((s, i) => (
                  <div key={i} className={`p-4 bg-slate-900/60 rounded-2xl border border-white/5 text-center transition-all hover:bg-white/5`}>
                    <p className="text-[7px] font-black text-slate-500 uppercase mb-1 tracking-widest">{s.label}</p>
                    <p className={`text-sm font-black text-white`}>{s.val}</p>
                  </div>
                ))}
              </div>

              {/* Topic Mastery Matrix */}
              <div className="bg-slate-950/50 border border-white/5 rounded-[2.5rem] p-8">
                <p className="text-[10px] font-black text-brand-tertiary uppercase tracking-[0.2em] mb-6">Pedagogical Mastery Analysis</p>
                <div className="space-y-4">
                  {Array.isArray(insights.metrics?.synchronization?.topic_mastery) && insights.metrics.synchronization.topic_mastery.length > 0 ? insights.metrics.synchronization.topic_mastery.map((m: any, i: number) => (
                    <div key={i}>
                      <div className="flex justify-between text-[10px] font-bold text-slate-400 mb-2">
                        <span>{m.topic} <span className="text-[8px] text-slate-600 ml-2">({m.volume} attempts)</span></span>
                        <span className={m.status === 'Elite' ? 'text-brand-primary' : 'text-indigo-400'}>{m.status} • {m.accuracy}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-900 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${m.accuracy}%` }}
                          className={`h-full ${m.accuracy > 90 ? 'bg-brand-primary' : 'bg-brand-tertiary'}`}
                        />
                      </div>
                    </div>
                  )) : (
                    <p className="text-[9px] text-slate-500 italic">No topic mastery data detected in current cycle.</p>
                  )}
                </div>
              </div>

              {/* Activity Timeline Trace */}
              <div className="bg-slate-950/50 border border-white/5 rounded-[2.5rem] p-8">
                <p className="text-[10px] font-black text-emerald-400 uppercase tracking-[0.2em] mb-6">Activity Symmetry Trace (Last 30 Cycles)</p>
                <div className="flex items-end justify-between h-20 gap-1 px-2">
                  {(insights.metrics.timeline || []).map((d: any, i: number) => (
                    <div key={i} className="flex-1 group relative">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${Math.min((d.activity || 0) * 20, 100)}%` }}
                        className={`w-full rounded-t-sm ${(d.activity || 0) > 0 ? 'bg-emerald-500/40 hover:bg-emerald-400 border-x border-emerald-500/20' : 'bg-white/5'}`}
                      />
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block bg-slate-900 border border-white/10 p-2 rounded-lg text-[8px] text-white whitespace-nowrap z-10 shadow-2xl">
                        {d.date}: {d.activity || 0} Intels
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-8 bg-brand-primary/5 border border-brand-primary/20 rounded-[2.5rem] relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-brand-primary/10 blur-[60px] -mr-16 -mt-16" />
                <div className="absolute bottom-0 left-0 w-32 h-32 bg-brand-tertiary/5 blur-[50px] -ml-16 -mb-16" />

                <div className="flex justify-between items-center mb-4">
                  <p className="text-[10px] font-black text-brand-primary uppercase tracking-[0.2em] flex items-center gap-2">
                    <Sparkles size={12} className="text-brand-primary" /> AI Pedagogical Growth Narrative
                  </p>
                  <button
                    onClick={handleGenerateAtlas}
                    disabled={generatingAtlas}
                    className="bg-brand-primary/10 hover:bg-brand-primary hover:text-slate-950 text-brand-primary px-3 py-1.5 rounded-lg text-[8px] font-black uppercase tracking-widest transition-all border border-brand-primary/20 disabled:opacity-50"
                  >
                    {generatingAtlas ? (
                      <div className="flex items-center gap-1.5">
                        <Loader2 size={10} className="animate-spin" /> Analyzing...
                      </div>
                    ) : (
                      'Enrich Atlas'
                    )}
                  </button>
                </div>

                <p className="text-xs font-bold text-slate-300 leading-relaxed italic relative z-10 transition-all group-hover:text-white">
                  "{insights.ai_narrative || "Synthesizing neural progress patterns for executive summary..."}"
                </p>

                {insights.metrics.study_path && insights.metrics.study_path.length > 0 && (
                  <div className="mt-6 border-t border-white/10 pt-4 relative z-10">
                    <p className="text-[10px] font-black text-brand-tertiary uppercase tracking-[0.2em] mb-3">AI Recommended Study Path</p>
                    <div className="flex gap-2 max-w-full overflow-x-auto pb-2">
                      {(Array.isArray(insights.metrics?.study_path) ? insights.metrics.study_path : []).map((path: any, i: number) => (
                        <div key={i} className="flex-none bg-slate-900 border border-brand-tertiary/20 px-4 py-3 rounded-xl min-w-[200px]">
                          <p className="text-[9px] text-slate-400 uppercase tracking-widest mb-1 font-bold">{path.chapter || "Fundamentals"}</p>
                          <p className="text-xs font-black text-slate-200 truncate">{path.name}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Detailed Log Fragment */}
              <div className="bg-slate-950/50 border border-white/5 rounded-[2.5rem] p-8">
                <div className="flex items-center justify-between mb-6">
                  <p className="text-[10px] font-black text-brand-primary uppercase tracking-[0.2em]">Neural Execution Logs (Last 25 Fragments)</p>
                  <div className="flex gap-2">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[8px] font-bold text-indigo-400">
                      <div className="w-1 h-1 rounded-full bg-indigo-400 animate-pulse" /> QUIZ
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[8px] font-bold text-emerald-400">
                      <div className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" /> CODE
                    </div>
                  </div>
                </div>

                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {Array.isArray(insights.raw_logs) && insights.raw_logs.map((log: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5 hover:border-white/10 transition-all group">
                      <div className="flex items-center gap-4">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-[8px] ${log.type === 'QUIZ' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-emerald-500/20 text-emerald-400'
                          }`}>
                          {log.type}
                        </div>
                        <div>
                          <p className="text-xs font-bold text-white group-hover:text-brand-primary transition-colors">{log.title}</p>
                          <div className="flex gap-2 mt-1">
                            <span className="text-[9px] text-slate-500 font-bold">{new Date(log.timestamp).toLocaleDateString()}</span>
                            <span className="text-[9px] text-slate-700 font-bold">|</span>
                            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">{log.type}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-black text-white">{log.result}</p>
                        <p className="text-[9px] text-slate-500 font-bold flex items-center justify-end gap-1"><Clock size={10} /> {log.efficiency || 'Neural Fast-Path'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-10 bg-slate-900/40 rounded-[2.5rem] border border-slate-800 text-center animate-pulse">
              <p className="text-[10px] font-black text-slate-500 uppercase">Synchronicity Link Severed</p>
            </div>
          )}
        </div>

        <button onClick={onClose} className="w-full py-5 bg-white/5 border border-white/5 rounded-3xl font-black uppercase tracking-widest text-xs text-white hover:bg-white/10 transition-all flex items-center justify-center gap-2">
          <BadgeCheck size={16} /> Acknowledge Intell Sync
        </button>
      </motion.div>
    </div>
  );
}

// ─── System Health Panel ─────────────────────────────────────────────────────
// Replaces hardcoded "Cluster Operational" static HTML with real API data

export function CreationModal({ type, onClose, onSubmit }: { type: string, onClose: () => void, onSubmit: (name: string) => void }) {
  const [name, setName] = React.useState('');
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-md" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative bg-slate-900 border border-white/10 rounded-[2.5rem] p-10 w-full max-w-md shadow-2xl"
      >
        <h3 className="text-2xl font-black text-white mb-6">Create New {type}</h3>
        <input
          autoFocus
          className="w-full bg-slate-800 border border-white/5 rounded-2xl p-5 text-white mb-6"
          placeholder={`${type} Name`}
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && name.trim() && onSubmit(name)}
        />
        <div className="flex gap-4">
          <button onClick={onClose} className="flex-1 py-4 bg-white/5 text-slate-400 rounded-2xl font-black">Cancel</button>
          <button
            disabled={!name.trim()}
            onClick={() => onSubmit(name)}
            className="flex-1 py-4 bg-indigo-600 text-white rounded-2xl font-black disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </motion.div>
    </div>
  );
}


