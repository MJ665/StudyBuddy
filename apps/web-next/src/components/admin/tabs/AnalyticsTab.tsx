'use client';
/* Extracted verbatim from LDAdminDashboard.tsx (5b decomposition). */
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
import ApiService, { ExecutiveSummary, BatchInsights } from '../../../services/ApiService';
import { useToast } from '../../ui/Toast';
import AssignmentCreationModal from '../../dashboard/AssignmentCreationModal';
import CourseEnrollmentModal from '../../dashboard/CourseEnrollmentModal';
import CodingQuestionModal from '../../dashboard/CodingQuestionModal';
import BankCreationModal from '../../dashboard/BankCreationModal';
import NotificationCenter from '../../common/NotificationCenter';
import { ComparisonChart, CompositeHealthGauge, EngagementDecayWidget, PerformanceDistributionChart, LeaderboardTable } from '../../dashboard/AnalyticsCharts';
import UserIntelPanel from '../../dashboard/UserIntelPanel';
import QuestionManagement from '../../dashboard/QuestionManagement';
import QuestionReportUI from '../../admin/QuestionReportUI';
import DataIntegrityDashboard from '../../dashboard/DataIntegrityDashboard';
import SystemHealthMonitor from '../../dashboard/SystemHealthMonitor';
import { StatCard, OrgNode, DeptNode, SystemHealthPanel, PerformanceMetricGrid } from '../../admin/AdminWidgets';
import { ResourceModal, DeleteModal, BulkAddModal, UserDetailsModal, CreationModal } from '../../admin/AdminModals';
import { AuditLogTable, EmailLogTable, QuestionReportTable, SecurityPulse } from '../../admin/AdminTables';

const filterTree = (nodes: any[], term: string): any[] => {
  if (!term || term.trim() === '') return nodes;
  const t = term.toLowerCase().trim();

  return nodes.map(node => {
    const name = (node.name || '').toLowerCase().trim();
    const matches = name.includes(t);

    // Recursive filtering for all possible child types
    const filteredDepts = node.departments ? filterTree(node.departments, term) : [];
    const filteredVerts = node.verticals ? filterTree(node.verticals, term) : [];
    const filteredBatches = node.batches ? filterTree(node.batches, term) : [];
    const filteredGroups = node.groups ? node.groups.filter((g: any) => (g.name || '').toLowerCase().trim().includes(t)) : [];

    // Return node if it matches OR any of its children match
    if (matches || filteredDepts.length > 0 || filteredVerts.length > 0 || filteredBatches.length > 0 || filteredGroups.length > 0) {
      return {
        ...node,
        departments: filteredDepts,
        verticals: filteredVerts,
        batches: filteredBatches,
        groups: filteredGroups
      };
    }
    return null;
  }).filter(Boolean);
};

import type { AdminTabCtx } from './types';

export default function AnalyticsTab({ ctx }: { ctx: AdminTabCtx }) {
  const { toast, loading,
    setLoading,
    tree,
    setTree,
    stats,
    setStats,
    expandedNodes,
    setExpandedNodes,
    showAddModal,
    setShowAddModal,
    showEditModal,
    setShowEditModal,
    showDeleteConfirm,
    setShowDeleteConfirm,
    showTaskModal,
    setShowTaskModal,
    taskData,
    setTaskData,
    ADMIN_TABS,
    activeTab,
    setActiveTabState,
    setActiveTab,
    users,
    setUsers,
    userSearch,
    setUserSearch,
    roleFilter,
    setRoleFilter,
    verticalFilter,
    setVerticalFilter,
    batchFilter,
    setBatchFilter,
    groupFilter,
    setGroupFilter,
    showAssignmentModal,
    setShowAssignmentModal,
    showCourseModal,
    setShowCourseModal,
    showCodingModal,
    setShowCodingModal,
    showBankModal,
    setShowBankModal,
    courses,
    setCourses,
    selectedUserDetails,
    setSelectedUserDetails,
    view,
    setView,
    nodeDetails,
    setNodeDetails,
    onboardingData,
    setOnboardingData,
    passwordPatternInline,
    setPasswordPatternInline,
    processing,
    setProcessing,
    individualUser,
    setIndividualUser,
    promoteId,
    setPromoteId,
    promoteRole,
    setPromoteRole,
    selectedUserIds,
    setSelectedUserIds,
    bulkProcessing,
    setBulkProcessing,
    newCourseName,
    setNewCourseName,
    addingCourse,
    setAddingCourse,
    bankCourseId,
    setBankCourseId,
    auditSubTab,
    setAuditSubTab,
    selectedAnalyticsBatch,
    setSelectedAnalyticsBatch,
    batchIntel,
    setBatchIntel,
    fetchingInsights,
    setFetchingInsights,
    executiveSummary,
    setExecutiveSummary,
    globalInsights,
    setGlobalInsights,
    fetchingGlobal,
    setFetchingGlobal,
    globalSummary,
    setGlobalSummary,
    codingQuestions,
    setCodingQuestions,
    addingCoding,
    setAddingCoding,
    codingLoading,
    setCodingLoading,
    codingFields,
    setCodingFields,
    getAllGroups,
    findGroupInTree,
    allPossibleGroups,
    getAllBatches,
    allPossibleBatches,
    fetchData,
    toggleNode,
    handleAdd,
    handleUpdateResource,
    handleDeleteResource,
    handleAddCourse,
    handleCreateCodingQuestion,
    fetchCodingQuestions,
    handleFetchBatchInsights,
    handleFetchGlobalInsights,
    globalMetrics,
    setGlobalMetrics,
    handleBulkAction,
    handleEmergencyReset,
    filteredUsers,
    user,
    onLogout,
    onViewReport,
    onViewPremium } = ctx;
  return (
<>
              <motion.div
                key="analytics"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                    <CompositeHealthGauge />
                  </div>
                  <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                    <EngagementDecayWidget />
                  </div>
                </div>

                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <h3 className="text-xl font-black text-white mb-6">Strategic Sector Leaderboard</h3>
                  <LeaderboardTable groupId={1} onIntel={onViewPremium} /> {/* Mock Group ID 1 for now */}
                </div>

                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <PerformanceDistributionChart />
                </div>

                <div className="p-8 bg-indigo-500/5 border border-indigo-500/20 rounded-[3rem] relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 blur-[100px] -mr-32 -mt-32" />
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8 gap-6">
                    <div>
                      <h3 className="text-xl font-black text-white">Batch Executive Strategy</h3>
                      <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mt-1">AI-Powered Cross-Cohort Synthesis</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <select
                        value={selectedAnalyticsBatch || ''}
                        onChange={(e) => setSelectedAnalyticsBatch(e.target.value ? parseInt(e.target.value) : null)}
                        className="bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-white outline-none min-w-[200px]"
                      >
                        <option value="">Select Cohort...</option>
                        {allPossibleBatches.map(b => (
                          <option key={b.id} value={b.id}>{b.context ? `${b.context} / ` : ''}{b.name}</option>
                        ))}
                      </select>
                      <button
                        disabled={!selectedAnalyticsBatch || fetchingInsights}
                        onClick={() => handleFetchBatchInsights(false)}
                        className="px-6 py-3 bg-brand-primary text-slate-950 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-primary/90 transition-all shadow-lg shadow-brand-primary/20 flex items-center gap-2 disabled:opacity-30"
                      >
                        {fetchingInsights ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                        Sync Intel
                      </button>
                      <button
                        disabled={!selectedAnalyticsBatch || fetchingInsights}
                        onClick={() => handleFetchBatchInsights(true)}
                        className="p-3 bg-white/5 border border-white/5 text-slate-500 hover:text-white rounded-xl transition-all disabled:opacity-30"
                        title="Force Neural Refresh (Bypass Cache)"
                      >
                        <RefreshCw size={16} className={fetchingInsights ? "animate-spin" : ""} />
                      </button>
                    </div>
                  </div>

                  {executiveSummary && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mb-8 p-6 bg-white/5 border border-white/5 rounded-2xl italic text-xs text-slate-300 leading-relaxed border-l-4 border-l-brand-primary"
                    >
                      "{executiveSummary}"
                    </motion.div>
                  )}
                  {batchIntel?.fullMetrics?.metrics && (
                    <div className="mb-10 space-y-8">
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center bg-slate-900/40 border border-white/5 p-8 rounded-[2.5rem] relative overflow-hidden group">
                        <div className="absolute inset-0 bg-brand-primary/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                        <div className="lg:col-span-5">
                          <p className="text-[10px] font-black text-brand-primary uppercase tracking-[0.2em] mb-6">Cohort Neural Fingerprint</p>
                          <div className="grid grid-cols-2 gap-4">
                            {[
                              { m: batchIntel.fullMetrics.metrics.m02_overall_accuracy, icon: <Target size={14} /> },
                              { m: batchIntel.fullMetrics.metrics.m17_velocity, icon: <TrendingUp size={14} /> },
                              { m: batchIntel.fullMetrics.metrics.m18_consistency, icon: <Activity size={14} /> },
                              { m: batchIntel.fullMetrics.metrics.m03_cognitive_diversity, icon: <Brain size={14} /> },
                              { m: batchIntel.fullMetrics.metrics.m26_talent_density, icon: <Trophy size={14} /> },
                              { m: batchIntel.fullMetrics.metrics.m29_risk_profile, icon: <Shield size={14} /> }
                            ].filter(x => x.m).map((item, idx) => (
                              <div key={idx} className="bg-slate-950/60 p-4 rounded-2xl border border-white/5 hover:border-brand-primary/30 transition-all">
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="text-brand-primary/60">{item.icon}</span>
                                  <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest truncate">{item.m.label}</p>
                                </div>
                                <p className="text-xl font-black text-white">{item.m.value}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="lg:col-span-7 h-80 relative">
                          <div className="absolute inset-0 flex items-center justify-center opacity-10">
                            <Sparkles size={200} className="text-brand-primary animate-pulse" />
                          </div>
                          <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                              { subject: "Accuracy", value: batchIntel.fullMetrics.metrics.m02_overall_accuracy?.raw || 0 },
                              { subject: "Consistency", value: batchIntel.fullMetrics.metrics.m18_consistency?.raw || 0 },
                              { subject: "Velocity", value: Math.min(100, Math.max(0, (batchIntel.fullMetrics.metrics.m17_velocity?.raw || 0) * 10 + 50)) },
                              { subject: "Diversity", value: batchIntel.fullMetrics.metrics.m03_cognitive_diversity?.raw || 0 },
                              { subject: "Density", value: batchIntel.fullMetrics.metrics.m26_talent_density?.raw || 0 },
                              { subject: "Stability", value: 100 - (batchIntel.fullMetrics.metrics.m29_risk_profile?.raw || 0) },
                            ]}>
                              <PolarGrid stroke="rgba(255,255,255,0.05)" />
                              <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 10, fontWeight: 900 }} />
                              <Radar name="Cohort" dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={3} />
                            </RadarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>


                      <div className="bg-white/5 border border-white/5 p-8 rounded-3xl">
                        <h4 className="text-[10px] font-black text-brand-primary uppercase tracking-[0.2em] mb-6">High-Fidelity Metric Matrix (30 Vectors)</h4>
                        <PerformanceMetricGrid metrics={batchIntel.fullMetrics.metrics} />
                      </div>
                    </div>
                  )}

                  {(batchIntel?.insights || []).length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {(Array.isArray(batchIntel?.insights) ? batchIntel.insights : []).map((insight: any, idx: number) => (
                        <div key={idx} className="p-6 bg-slate-900/50 border border-white/5 rounded-[2rem] hover:border-brand-primary/30 transition-all relative overflow-hidden group">
                          <div className="flex items-center justify-between mb-4">
                            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-tighter ${insight.impact === 'High' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                              insight.impact === 'Medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                                'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              }`}>
                              {insight.impact} Impact
                            </span>
                            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">{insight.category}</span>
                          </div>
                          <h4 className="text-sm font-black text-white mb-2 group-hover:text-brand-primary transition-colors">{insight.dimension}</h4>
                          <p className="text-[11px] text-slate-400 leading-relaxed mb-4">{insight.observation}</p>
                          <div className="pt-4 border-t border-white/5">
                            <p className="text-[9px] font-black text-brand-primary uppercase tracking-widest mb-2">Executive Action</p>
                            <p className="text-[10px] font-bold text-slate-300 italic">{insight.actionable_step}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 leading-relaxed max-w-2xl">
                      AI-powered strategic summaries aggregate performance vectors across all synchronized groups to identify high-risk cohorts and high-potential talent pipelines for executive intervention. Select a cohort and synchronize to begin.
                    </p>
                  )}
                </div>

                <div className="p-8 bg-purple-500/5 border border-purple-500/20 rounded-[3rem] relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/10 blur-[100px] -mr-32 -mt-32" />
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8 gap-6">
                    <div>
                      <h3 className="text-xl font-black text-white">Global Organization Intelligence</h3>
                      <p className="text-[10px] text-purple-400 font-black uppercase tracking-[0.3em] mt-1">Cross-Sector Neural Synthesis</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <button
                        disabled={fetchingGlobal}
                        onClick={() => handleFetchGlobalInsights(false)}
                        className="px-6 py-3 bg-purple-600 text-white rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-purple-500 transition-all shadow-lg shadow-purple-600/20 flex items-center gap-2 disabled:opacity-30"
                      >
                        {fetchingGlobal ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
                        Sync Global Intel
                      </button>
                      <button
                        disabled={fetchingGlobal}
                        onClick={() => handleFetchGlobalInsights(true)}
                        className="p-3 bg-white/5 border border-white/5 text-slate-500 hover:text-white rounded-xl transition-all disabled:opacity-30"
                        title="Force Global Neural Refresh (Bypass Cache)"
                      >
                        <RefreshCw size={16} className={fetchingGlobal ? "animate-spin" : ""} />
                      </button>
                    </div>
                  </div>

                  {globalSummary && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mb-8 p-8 bg-purple-500/5 border border-purple-500/10 rounded-[2.5rem] italic text-sm text-slate-300 leading-relaxed border-l-4 border-l-purple-500"
                    >
                      "{globalSummary}"
                    </motion.div>
                  )}

                  {globalMetrics?.metrics && (
                    <div className="mb-10 space-y-8">
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center bg-slate-900/40 border border-white/5 p-8 rounded-[2.5rem] relative overflow-hidden group">
                        <div className="absolute inset-0 bg-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                        <div className="lg:col-span-5">
                          <p className="text-[10px] font-black text-purple-400 uppercase tracking-[0.2em] mb-6">Global Performance Fingerprint</p>
                          <div className="grid grid-cols-2 gap-4">
                            {[
                              { m: globalMetrics.metrics.m02_overall_accuracy, icon: <Target size={14} /> },
                              { m: globalMetrics.metrics.m17_velocity, icon: <TrendingUp size={14} /> },
                              { m: globalMetrics.metrics.m18_consistency, icon: <Activity size={14} /> },
                              { m: globalMetrics.metrics.m03_cognitive_diversity, icon: <Brain size={14} /> },
                              { m: globalMetrics.metrics.m26_talent_density, icon: <Trophy size={14} /> },
                              { m: globalMetrics.metrics.m29_risk_profile, icon: <Shield size={14} /> }
                            ].filter(x => x.m).map((item, idx) => (
                              <div key={idx} className="bg-slate-950/60 p-4 rounded-2xl border border-white/5 hover:border-purple-500/30 transition-all text-left">
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="text-purple-400/60">{item.icon}</span>
                                  <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest truncate">{item.m.label}</p>
                                </div>
                                <p className="text-xl font-black text-white">{item.m.value}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="lg:col-span-7 h-80 relative">
                          <div className="absolute inset-0 flex items-center justify-center opacity-10">
                            <Brain size={200} className="text-purple-500 animate-pulse" />
                          </div>
                          <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                              { subject: "Accuracy", value: globalMetrics.metrics.m02_overall_accuracy?.raw || 0 },
                              { subject: "Consistency", value: globalMetrics.metrics.m18_consistency?.raw || 0 },
                              { subject: "Velocity", value: Math.min(100, Math.max(0, (globalMetrics.metrics.m17_velocity?.raw || 0) * 10 + 50)) },
                              { subject: "Diversity", value: globalMetrics.metrics.m03_cognitive_diversity?.raw || 0 },
                              { subject: "Density", value: globalMetrics.metrics.m26_talent_density?.raw || 0 },
                              { subject: "Stability", value: 100 - (globalMetrics.metrics.m29_risk_profile?.raw || 0) },
                            ]}>
                              <PolarGrid stroke="rgba(255,255,255,0.05)" />
                              <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 10, fontWeight: 900 }} />
                              <Radar name="Global" dataKey="value" stroke="#a855f7" fill="#a855f7" fillOpacity={0.2} strokeWidth={3} />
                            </RadarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>


                      <div className="bg-white/5 border border-white/5 p-8 rounded-3xl">
                        <h4 className="text-[10px] font-black text-purple-400 uppercase tracking-[0.2em] mb-6">Cross-Organization Metric Matrix (30 Vectors)</h4>
                        <PerformanceMetricGrid metrics={globalMetrics.metrics} />
                      </div>
                    </div>
                  )}

                  {(Array.isArray(globalInsights) ? globalInsights : []).length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {(Array.isArray(globalInsights) ? globalInsights : []).map((insight, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: idx * 0.05 }}
                          className="p-6 bg-slate-900/40 border border-white/5 rounded-[2.5rem] hover:border-purple-500/30 transition-all relative overflow-hidden group shadow-xl hover:shadow-purple-500/5"
                        >
                          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 blur-3xl -mr-16 -mt-16 group-hover:bg-purple-500/10 transition-all" />
                          <div className="flex items-center justify-between mb-4 relative z-10">
                            <span className={`px-3 py-1 rounded-full text-[8px] font-black uppercase tracking-tighter shadow-sm border ${insight.impact === 'High' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' :
                              insight.impact === 'Medium' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              }`}>
                              {insight.impact} Impact
                            </span>
                            <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">{insight.category}</span>
                          </div>
                          <h4 className="text-sm font-black text-white mb-2 group-hover:text-purple-400 transition-colors relative z-10">{insight.dimension}</h4>
                          <p className="text-[11px] text-slate-400 leading-relaxed mb-4 relative z-10">{insight.observation}</p>
                          <div className="pt-4 border-t border-white/5 relative z-10">
                            <p className="text-[9px] font-black text-purple-400 uppercase tracking-widest mb-2 flex items-center gap-2">
                              <Sparkles size={10} /> System Mandate
                            </p>
                            <p className="text-[10px] font-bold text-slate-200 italic bg-white/5 p-3 rounded-xl border border-white/5">{insight.actionable_step}</p>
                          </div>
                        </motion.div>

                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 leading-relaxed max-w-2xl">
                      Global neural synthesis analyzes performance trends across all organizations, departments, and verticals to surface macro-patterns and strategic opportunities for L&D leadership.
                    </p>
                  )}
                </div>
              </motion.div>
</>
  );
}
