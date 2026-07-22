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

export function StatCard({ icon, label, value, trend, color }: any) {
  const colors: any = {
    indigo: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
    emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
  };
  return (
    <div className={`p-8 rounded-[2.5rem] border ${colors[color]} shadow-xl flex items-center justify-between`}>
      <div>
        <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60 mb-2">{label}</p>
        <p className="text-4xl font-black text-white">{value}</p>
      </div>
      <div className="flex flex-col items-end gap-3">
        <div className="p-4 bg-slate-950/40 rounded-2xl border border-white/5">{icon}</div>
        <span className="text-[9px] font-black uppercase tracking-widest opacity-60">{trend}</span>
      </div>
    </div>
  );
}


export function OrgNode({ org, expanded, onToggle, onAdd, onEdit, onDelete, onAction, nodeDetails, expandedNodes, toggleNode, onViewReport }: any) {
  return (
    <div className="bg-surface-dim/40 border border-surface-bright rounded-[2.5rem] overflow-hidden">
      <div className="flex items-center justify-between p-6 hover:bg-white/5 cursor-pointer transition-all" onClick={onToggle}>
        <div className="flex items-center gap-6">
          <div className="w-12 h-12 rounded-2xl bg-brand-primary/10 flex items-center justify-center text-brand-primary">
            <Building2 size={24} />
          </div>
          <div>
            <p className="text-lg font-black text-white">{org.name}</p>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">{org.departments.length} Departments Managed</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={(e) => { e.stopPropagation(); onEdit({ type: 'Org', id: org.id, name: org.name }); }}
            className="p-3 bg-white/5 text-slate-400 rounded-xl hover:bg-white/10 hover:text-white transition-all"
            title="Edit Organization"
          >
            <Settings size={18} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete({ type: 'Org', id: org.id, name: org.name }); }}
            className="p-3 bg-rose-500/10 text-rose-400 rounded-xl hover:bg-rose-500 hover:text-white transition-all"
            title="Delete Organization"
          >
            <Trash2 size={18} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onAction('MANDATE', org.id, org.name, 'Organization'); }}
            className="p-3 bg-brand-primary/10 text-brand-primary rounded-xl hover:bg-brand-primary hover:text-slate-950 transition-all"
            title="Assign Mandate"
          >
            <Target size={20} />
          </button>
          <div className="w-px h-8 bg-white/5 mx-1" />
          <button onClick={(e) => { e.stopPropagation(); onAdd({ type: 'Dept', parentId: org.id }); }} className="p-3 bg-brand-primary/10 text-brand-primary rounded-xl hover:bg-brand-primary hover:text-slate-950 transition-all">
            <Plus size={20} />
          </button>
          {expanded ? <ChevronDown size={24} className="text-on-surface-variant" /> : <ChevronRight size={24} className="text-on-surface-variant" />}
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="px-6 pb-6 space-y-4">
            {org.departments.map((dept: any) => (
              <DeptNode
                key={dept.id}
                dept={dept}
                expanded={expandedNodes.has(`dept-${dept.id}`)}
                onToggle={() => toggleNode(`dept-${dept.id}`)}
                onAdd={onAdd}
                onEdit={onEdit}
                onDelete={onDelete}
                onAction={onAction}
                nodeDetails={nodeDetails}
                expandedNodes={expandedNodes}
                toggleNode={toggleNode}
                onViewReport={onViewReport}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


export function DeptNode({ dept, expanded, onToggle, onAdd, onEdit, onDelete, onAction, nodeDetails, expandedNodes, toggleNode, onViewReport }: any) {
  return (
    <div className="bg-surface-container/60 rounded-3xl border border-surface-bright/50 overflow-hidden">
      <div className="flex items-center justify-between p-4 hover:bg-white/5 cursor-pointer transition-all" onClick={onToggle}>
        <div className="flex items-center gap-4">
          <Layers size={18} className="text-indigo-400" />
          <p className="font-bold text-white text-sm">{dept.name}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={(e) => { e.stopPropagation(); onEdit({ type: 'Dept', id: dept.id, name: dept.name }); }}
            className="p-2 text-slate-500 hover:text-white transition-all"
            title="Edit Department"
          >
            <Settings size={14} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete({ type: 'Dept', id: dept.id, name: dept.name }); }}
            className="p-2 text-rose-500/50 hover:text-rose-400 transition-all"
            title="Delete Department"
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onAction('MANDATE', dept.id, dept.name, 'Department'); }}
            className="p-2 bg-brand-primary/10 text-brand-primary rounded-lg hover:bg-brand-primary hover:text-slate-950 transition-all"
            title="Assign Mandate"
          >
            <Target size={16} />
          </button>
          <div className="w-px h-4 bg-white/5 mx-1" />
          <button onClick={(e) => { e.stopPropagation(); onAdd({ type: 'Vertical', parentId: dept.id }); }} className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg"><Plus size={16} /></button>
          {expanded ? <ChevronDown size={18} className="text-slate-500" /> : <ChevronRight size={18} className="text-slate-500" />}
        </div>
      </div>
      {expanded && (
        <div className="px-6 pb-4 pt-2 space-y-4 border-l-2 border-indigo-500/20 ml-6">
          {dept.verticals.map((v: any) => (
            <div key={v.id} className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-black uppercase text-slate-500 tracking-widest">{v.name}</span>
                  <button
                    onClick={() => onEdit({ type: 'Vertical', id: v.id, name: v.name })}
                    className="text-slate-700 hover:text-slate-400"
                  >
                    <Settings size={12} />
                  </button>
                  <button
                    onClick={() => onDelete({ type: 'Vertical', id: v.id, name: v.name })}
                    className="text-rose-900 hover:text-rose-500"
                  >
                    <Trash2 size={12} />
                  </button>
                  <button
                    title="Assign Mandate"
                    onClick={() => onAction('MANDATE', v.id, v.name, 'Vertical')}
                    className="text-brand-primary hover:text-white transition-colors"
                  >
                    <Target size={12} />
                  </button>
                </div>
                <button onClick={() => onAdd({ type: 'Batch', parentId: v.id })} className="text-amber-500 hover:text-amber-400"><Plus size={14} /></button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {v.batches.map((b: any) => (
                  <div key={b.id} className="bg-slate-900 border border-slate-800 p-5 rounded-3xl">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-[10px] font-black text-amber-500 uppercase tracking-widest">{b.name}</p>
                          <button onClick={() => onEdit({ type: 'Batch', id: b.id, name: b.name })} className="text-slate-700 hover:text-slate-500"><Settings size={10} /></button>
                          <button onClick={() => onDelete({ type: 'Batch', id: b.id, name: b.name })} className="text-rose-900 hover:text-rose-700"><Trash2 size={10} /></button>
                        </div>
                        <p className="text-[8px] text-slate-600 font-bold uppercase mt-1">Cohort Managed</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          title="Assign Mandate"
                          onClick={() => onAction('MANDATE', b.id, b.name, 'Batch')}
                          className="p-1.5 bg-brand-primary/10 text-brand-primary rounded-lg hover:bg-brand-primary hover:text-slate-950 transition-all"
                        >
                          <Target size={14} />
                        </button>
                        <button onClick={() => b.id ? (onViewReport ? onViewReport(b.id) : window.open(`/api/reports/batch/${b.id}/summary`, '_blank')) : null} className="p-1.5 bg-white/5 text-slate-400 rounded-lg hover:text-white transition-all"><TrendingUp size={14} /></button>
                        <button onClick={() => onAdd({ type: 'Group', parentId: b.id })} className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg transition-all"><Plus size={14} /></button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {b.groups.map((g: any) => (
                        <div
                          key={g.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            onAction('GROUP_SELECT', g.id, g.name);
                          }}
                          className={`px-4 py-2 rounded-2xl flex items-center gap-3 cursor-pointer transition-all border ${nodeDetails?.id === g.id
                            ? 'bg-brand-primary text-slate-950 border-brand-primary shadow-lg shadow-brand-primary/20'
                            : 'bg-white/5 border-white/5 text-slate-400 hover:border-brand-primary/30 hover:text-white'
                            }`}
                        >
                          <div className={`w-2 h-2 rounded-full ${nodeDetails?.id === g.id ? 'bg-slate-950' : 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]'}`} />
                          <span className="text-[10px] font-black uppercase tracking-widest">{g.name}</span>

                          {nodeDetails?.id === g.id ? (
                            <div className="flex items-center gap-1.5 ml-2 border-l border-slate-950/20 pl-2">
                              <button title="Edit Group" onClick={(e) => { e.stopPropagation(); onEdit({ type: 'Group', id: g.id, name: g.name }); }} className="hover:scale-110 transition-transform"><Settings size={12} /></button>
                              <button title="Delete Group" onClick={(e) => { e.stopPropagation(); onDelete({ type: 'Group', id: g.id, name: g.name }); }} className="hover:scale-110 transition-transform text-rose-900 hover:text-rose-500"><Trash2 size={12} /></button>
                              <div className="w-px h-3 bg-slate-950/20 mx-0.5" />
                              <button title="Add Member" onClick={(e) => { e.stopPropagation(); onAction('MEMBER_ADD', g.id, g.name); }} className="hover:scale-110 transition-transform"><UserPlus size={12} /></button>
                              <button title="Add Mentor" onClick={(e) => { e.stopPropagation(); onAction('MENTOR_ADD', g.id, g.name); }} className="hover:scale-110 transition-transform"><ShieldCheck size={12} /></button>
                              <button title="Assign mandate" onClick={(e) => { e.stopPropagation(); onAction('MANDATE', g.id, g.name, 'Group'); }} className="hover:scale-110 transition-transform"><Target size={12} /></button>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


export function SystemHealthPanel({ stats }: { stats: any }) {
  const [health, setHealth] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(false);
  const [triggering, setTriggering] = React.useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const h = await ApiService.getSystemHealth();
      setHealth(h);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  const handleTrigger = async (taskName: string) => {
    setTriggering(taskName);
    try {
      await ApiService.triggerTask(taskName);
      fetchHealth();
    } catch (err: any) {
      console.error(err);
    } finally {
      setTriggering(null);
    }
  };

  const components = health?.components || {};
  const tasks = health?.tasks || {};

  const systemRows = [
    { label: 'AI Evaluation Engine', key: 'ai_engine', fallback: stats?.health_status || 'Checking...' },
    { label: 'Database Connection', key: 'database', fallback: 'Checking...' },
    { label: 'Cache Layer (Redis)', key: 'redis', fallback: 'Checking...' },
    { label: 'Email Service', key: 'email', fallback: 'Checking...' },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h5 className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-surface-bright pb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity size={12} className="text-emerald-400" /> Infrastructure Nodes
          </div>
          <button
            onClick={async () => {
              try {
                await ApiService.syncInfrastructure();
                fetchHealth();
              } catch (err) {
                console.error("Infrastructure sync failed", err);
              }
            }}
            className="flex items-center gap-1.5 text-brand-primary hover:text-white transition-colors"
          >
            <RefreshCw size={10} className={loading ? "animate-spin" : ""} /> Sync Nodes
          </button>
        </h5>
        {systemRows.map(({ label, key, fallback }) => {
          const status = components[key]?.status || fallback;
          const isOk = status === 'Operational';
          return (
            <div key={key} className="p-3 bg-surface-dim rounded-xl border border-surface-bright flex items-center justify-between">
              <p className="text-[9px] text-slate-500 font-black uppercase">{label}</p>
              <div className="text-[10px] font-bold text-white flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isOk ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]' : status === 'Checking...' ? 'bg-amber-400 animate-pulse' : 'bg-rose-400'}`} />
                {status}
              </div>
            </div>
          );
        })}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between border-b border-surface-bright pb-2">
          <h5 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
            <Terminal size={12} className="text-indigo-400" /> Automation Workers
          </h5>
          <button onClick={fetchHealth} disabled={loading} className="p-1 hover:bg-surface-bright rounded text-slate-500">
            <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {!health || Object.keys(tasks).length === 0 ? (
          <div className="p-4 text-center text-[10px] text-slate-600 font-bold italic">
            {loading ? 'Initializing telemetry...' : 'No active worker nodes detected.'}
          </div>
        ) : (
          Object.entries(tasks).map(([name, data]: [string, any]) => (
            <div key={name} className="p-3 bg-surface-dim rounded-xl border border-surface-bright group hover:border-indigo-500/30 transition-all">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[9px] text-indigo-400 font-black uppercase tracking-tighter truncate max-w-[150px]">{name.replace(/_/g, ' ')}</p>
                <button
                  onClick={() => handleTrigger(name)}
                  disabled={triggering === name}
                  className="p-1.5 bg-indigo-600/10 hover:bg-indigo-600/20 rounded-lg text-indigo-400 transition-colors"
                  title="Trigger Manual Run"
                >
                  {triggering === name ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} fill="currentColor" />}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className={`w-1.5 h-1.5 rounded-full ${data.status === 'success' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  <p className="text-[10px] text-white font-bold">{data.runs} runs</p>
                </div>
                <div className="flex items-center gap-1 text-slate-500">
                  <Clock size={8} />
                  <p className="text-[8px] font-bold">{data.last_run ? new Date(data.last_run).toLocaleTimeString() : 'Never'}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {health && (
        <div className="pt-2 text-[8px] text-slate-600 font-black text-right uppercase tracking-tighter">
          Kernel {health.version} · {new Date(health.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}


export function PerformanceMetricGrid({ metrics }: { metrics: any }) {
  if (!metrics) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {Object.entries(metrics).map(([key, data]: [string, any]) => {
        const typeColor = data.type === 'quantitative' ? 'text-indigo-400' : data.type === 'qualitative' ? 'text-purple-400' : 'text-amber-400';
        const bgColor = data.type === 'quantitative' ? 'bg-indigo-500/5' : data.type === 'qualitative' ? 'bg-purple-500/5' : 'bg-amber-500/5';

        return (
          <div key={key} className={`${bgColor} border border-white/5 rounded-2xl p-4 hover:border-white/20 transition-all group relative overflow-hidden`}>
            <div className="absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <Info size={12} className="text-slate-500" />
              <div className="absolute bottom-full right-0 mb-2 w-48 p-2 bg-slate-900 border border-white/10 rounded-lg text-[8px] text-slate-400 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50">
                {data.description}
              </div>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs group-hover:scale-110 transition-transform">{data.icon || '📊'}</span>
              <p className={`text-[9px] font-black uppercase tracking-widest ${typeColor} truncate`}>
                {data.label || key.replace(/_/g, ' ')}
              </p>
            </div>
            <p className="text-lg font-black text-white">{data.value}</p>

            {data.raw !== undefined && (
              <div className="mt-3 w-full h-1 bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full ${data.type === 'quantitative' ? 'bg-indigo-500' : 'bg-purple-500'} rounded-full transition-all duration-1000 shadow-[0_0_8px_rgba(99,102,241,0.4)]`}
                  style={{ width: `${Math.min(100, Math.max(0, data.raw))}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}








