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

export function AuditLogTable() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await ApiService.getAuditLogs();
      setLogs(Array.isArray(data) ? data : (data?.items || []));
    } catch (err) {
      console.error("Audit log synchronization failure", err);
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (!logs.length) return;
    const headers = ["ID", "Timestamp", "Actor Role", "Action", "Resource", "Details"];
    const rows = logs.map(log => [
      log.id,
      new Date(log.timestamp).toISOString(),
      log.actor_role,
      log.action,
      `${log.target_type}#${log.target_id}`,
      JSON.stringify(log.metadata).replace(/"/g, '""')
    ]);

    const csvContent = [headers, ...rows].map(e => e.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `StudyBuddy_AuditLog_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  if (loading) return <div className="p-20 flex justify-center"><Loader2 className="animate-spin text-brand-primary" /></div>;

  return (
    <div className="overflow-hidden">
      <div className="flex justify-end gap-3 mb-4">
        <button onClick={handleExportCSV} className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 text-emerald-400 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500/20 transition-all border border-emerald-500/20">
          <Download size={14} /> Export CSV
        </button>
        <button onClick={fetchLogs} className="flex items-center gap-2 px-4 py-2 bg-indigo-500/10 text-indigo-400 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-indigo-500/20 transition-all border border-indigo-500/20">
          <RefreshCw size={14} /> Refresh Log
        </button>
      </div>
      <div className="border border-surface-bright/30 rounded-2xl overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-bright/5 border-b border-surface-bright/30">
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Timestamp</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Administrator</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Action</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Resource</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Detail Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-bright/20">
            {(Array.isArray(logs) ? logs : []).map((log: any) => (
              <tr key={log.id} className="hover:bg-white/5 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex flex-col">
                    <span className="text-[10px] font-black text-white">{new Date(log.timestamp).toLocaleDateString()}</span>
                    <span className="text-[8px] font-bold text-slate-500 uppercase">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 text-[10px] font-black">
                      {log.actor_role?.[0]}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[10px] font-bold text-slate-300">{log.admin_name}</span>
                      <span className="text-[8px] font-bold text-slate-500 uppercase">{log.actor_role}</span>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-tight ${log.action.includes('PROMOTE') ? 'bg-amber-500/20 text-amber-400' :
                    log.action.includes('CREATE') ? 'bg-emerald-500/20 text-emerald-400' :
                      log.action.includes('DELETE') ? 'bg-rose-500/20 text-rose-400' :
                        'bg-slate-500/20 text-slate-400'
                    }`}>
                    {log.action}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-1 text-[9px] font-mono text-indigo-300/80">
                    <FileText size={12} /> {log.target_type}#{log.target_id}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <p className="text-[9px] text-slate-500 font-medium max-w-xs truncate">
                    {JSON.stringify(log.metadata)}
                  </p>
                </td>
              </tr>
            ))}
            {(Array.isArray(logs) ? logs : []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-20 text-center text-[10px] font-black uppercase tracking-widest text-slate-600 italic">
                  No administrative sessions recorded in current epoch.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


export function EmailLogTable() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await ApiService.getEmailLogs();
      setLogs(Array.isArray(data) ? data : (data?.items || []));
    } catch (err) {
      console.error("Email log synchronization failure", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-20 flex justify-center"><Loader2 className="animate-spin text-brand-primary" /></div>;

  return (
    <div className="overflow-hidden">
      <div className="flex justify-end gap-3 mb-4">
        <button onClick={fetchLogs} className="flex items-center gap-2 px-4 py-2 bg-indigo-500/10 text-indigo-400 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-indigo-500/20 transition-all border border-indigo-500/20">
          <RefreshCw size={14} /> Sync Communications
        </button>
      </div>
      <div className="border border-surface-bright/30 rounded-2xl overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-bright/5 border-b border-surface-bright/30">
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Timestamp</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Recipient</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Type</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Status</th>
              <th className="px-6 py-4 text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Subject Fragment</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-bright/20">
            {(Array.isArray(logs) ? logs : []).map((log: any) => (
              <tr key={log.id} className="hover:bg-white/5 transition-colors">
                <td className="px-6 py-4">
                  <p className="text-[10px] font-black text-white">{new Date(log.sent_at).toLocaleDateString()}</p>
                  <p className="text-[8px] font-bold text-slate-500 uppercase">{new Date(log.sent_at).toLocaleTimeString()}</p>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-col">
                    <span className="text-[10px] font-black text-slate-300">{log.user_name}</span>
                    <span className="text-[9px] font-medium text-slate-500">{log.recipient}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 text-[8px] font-black uppercase tracking-tight">
                    {log.type}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${log.status === 'sent' ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.4)]' : 'bg-rose-400'}`} />
                    <span className={`text-[9px] font-black uppercase ${log.status === 'sent' ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {log.status}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <p className="text-[9px] text-slate-400 font-medium truncate max-w-xs">{log.subject}</p>
                </td>
              </tr>
            ))}
            {(Array.isArray(logs) ? logs : []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-20 text-center text-[10px] font-black uppercase tracking-widest text-slate-600 italic">
                  No communication packets detected in current epoch.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


export function QuestionReportTable() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<boolean | undefined>(false); // Default to unresolved

  const fetchReports = async () => {
    setLoading(true);
    try {
      const res = await ApiService.getQuestionReports(filter);
      setReports(res);
    } catch (err) {
      console.error("Failed to fetch reports", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [filter]);

  const handleResolve = async (id: number) => {
    try {
      await ApiService.resolveQuestionReport(id);
      fetchReports();
    } catch (err) {
      alert("Failed to resolve report");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-4 mb-6">
        {[
          { label: 'Unresolved', value: false },
          { label: 'Resolved', value: true },
          { label: 'All Reports', value: undefined }
        ].map(opt => (
          <button
            key={String(opt.value)}
            onClick={() => setFilter(opt.value)}
            className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${filter === opt.value
              ? 'bg-rose-500/20 border border-rose-500/50 text-rose-400'
              : 'bg-slate-800 border border-white/5 text-slate-500 hover:text-slate-400'
              }`}
          >
            {opt.label}
          </button>
        ))}
        <button
          onClick={fetchReports}
          className="ml-auto p-2.5 bg-slate-800 border border-white/5 rounded-xl text-slate-500 hover:text-rose-400 transition-all"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="overflow-x-auto border border-white/5 rounded-3xl">
        <table className="w-full text-left">
          <thead className="bg-white/5">
            <tr>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Status</th>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Question</th>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Reason</th>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Reporter</th>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Date</th>
              <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {loading ? (
              <tr><td colSpan={6} className="px-6 py-20 text-center animate-pulse text-slate-600">Syncing quality logs...</td></tr>
            ) : reports.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-20 text-center text-slate-600 italic">No reports found matching criteria.</td></tr>
            ) : (Array.isArray(reports) ? reports : []).map(r => (
              <tr key={r.id} className="hover:bg-white/5 transition-all group">
                <td className="px-6 py-4">
                  {r.is_resolved ? (
                    <span className="flex items-center gap-1.5 text-emerald-400 text-[10px] font-black uppercase">
                      <Check size={12} /> Resolved
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-rose-400 text-[10px] font-black uppercase animate-pulse">
                      <AlertTriangle size={12} /> Pending
                    </span>
                  )}
                </td>
                <td className="px-6 py-4">
                  <p className="text-xs font-bold text-white line-clamp-1">{r.question_text}</p>
                  {r.comment && <p className="text-[10px] text-slate-500 mt-1 italic line-clamp-1">"{r.comment}"</p>}
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-black uppercase">
                    {r.reason.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-6 py-4 text-xs font-bold text-slate-400">
                  {r.reporter_name}
                </td>
                <td className="px-6 py-4 text-[10px] font-mono text-slate-600">
                  {new Date(r.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 text-right">
                  {!r.is_resolved && (
                    <button
                      onClick={() => handleResolve(r.id)}
                      className="px-4 py-2 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500 hover:text-slate-950 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border border-emerald-500/20"
                    >
                      Resolve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


export function SecurityPulse() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await ApiService.getSecurityStats();
        setStats(res);
      } catch (err) {
        console.error("Security Pulse synchronization failure", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) return <div className="animate-pulse flex gap-6 mb-8">
    {[1, 2, 3].map(i => <div key={i} className="flex-1 h-32 bg-surface-bright/10 rounded-[2rem]" />)}
  </div>;

  return (
    <div className="grid grid-cols-3 gap-6 mb-8">
      <div className="bg-slate-900 border border-white/5 p-8 rounded-[2rem] relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full -mr-8 -mt-8 blur-2xl group-hover:bg-indigo-500/10 transition-all" />
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">30D Governance Velocity</p>
        <h4 className="text-4xl font-black text-white">{stats?.thirty_day_velocity || 0}</h4>
        <p className="text-[8px] font-bold text-indigo-400 uppercase mt-2 tracking-tighter">Total administrative sessions</p>
      </div>
      <div className="bg-slate-900 border border-white/5 p-8 rounded-[2rem] relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full -mr-8 -mt-8 blur-2xl group-hover:bg-amber-500/10 transition-all" />
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Role Mutations</p>
        <h4 className="text-4xl font-black text-amber-400">{stats?.role_mutations || 0}</h4>
        <p className="text-[8px] font-bold text-amber-500/60 uppercase mt-2 tracking-tighter">System-wide privilege escalations</p>
      </div>
      <div className="bg-slate-900 border border-white/5 p-8 rounded-[2rem] relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full -mr-8 -mt-8 blur-2xl group-hover:bg-emerald-500/10 transition-all" />
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Active Governance Nodes</p>
        <div className="flex -space-x-2 mt-2">
          {stats?.active_governance_nodes?.map((node: string, i: number) => (
            <div key={i} className="w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-900 flex items-center justify-center text-[10px] font-black text-emerald-400" title={node}>
              {node[0]}
            </div>
          ))}
          {!stats?.active_governance_nodes?.length && <span className="text-[10px] font-black text-slate-600 italic uppercase">System Only</span>}
        </div>
        <p className="text-[8px] font-bold text-emerald-500/60 uppercase mt-2 tracking-tighter">Verified L&D Administrators</p>
      </div>
    </div>
  );
}


