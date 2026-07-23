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
import QuestionReportUI from '../admin/QuestionReportUI';
import DataIntegrityDashboard from '../dashboard/DataIntegrityDashboard';
import SystemHealthMonitor from '../dashboard/SystemHealthMonitor';
import { StatCard, OrgNode, DeptNode, SystemHealthPanel, PerformanceMetricGrid } from '../admin/AdminWidgets';
import { ResourceModal, DeleteModal, BulkAddModal, UserDetailsModal, CreationModal } from '../admin/AdminModals';
import { AuditLogTable, EmailLogTable, QuestionReportTable, SecurityPulse } from '../admin/AdminTables';

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

import type { AdminTabCtx } from './tabs/types';

export default function AdminOnboardingOverlay({ ctx }: { ctx: AdminTabCtx }) {
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
                key={view}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="bg-surface-container border border-surface-bright rounded-[3rem] p-10 shadow-2xl"
              >
                <div className="flex justify-between items-center mb-10">
                  <div>
                    <h3 className="text-3xl font-black text-white">{view === 'onboarding' ? 'Bulk Onboarding Protocol' : view === 'addUser' ? 'Ad-Hoc Member Registration' : 'Register Strategic Mentor'}</h3>
                    <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mt-2">Node: {nodeDetails?.name || 'Global Registry'}</p>
                  </div>
                  <button onClick={() => setView('dashboard')} className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-500 hover:text-white"><ArrowLeft size={24} /></button>
                </div>

                {view === 'onboarding' ? (
                  <div className="space-y-8">
                    <div>
                      <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Target Group Link</label>
                      <select
                        className="w-full bg-slate-900 border border-white/5 rounded-2xl p-5 text-white font-bold outline-none"
                        value={nodeDetails?.id || ''}
                        onChange={(e) => {
                          const id = parseInt(e.target.value);
                          const g = findGroupInTree(id, tree);
                          setNodeDetails({ type: 'GROUP', id, name: g?.name || 'Unknown' });
                        }}
                      >
                        <option value="">Select Target Synchronicity Point...</option>
                        {allPossibleGroups.map(g => (
                          <option key={g.id} value={g.id}>{g.context ? `${g.context} / ` : ''}{g.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-[10px] font-black uppercase text-slate-500 tracking-[0.2em]">Auth Pattern (e.g. &lt;name&gt;sig@123)</label>
                        <div className="flex gap-2">
                          {['<name>sigmoid@123', '<name>@2026', 'sigmoid@<year>'].map(tpl => (
                            <button
                              key={tpl}
                              onClick={() => setPasswordPatternInline(tpl)}
                              className="text-[8px] font-black uppercase px-2 py-1 bg-white/5 hover:bg-brand-primary hover:text-slate-950 rounded-lg transition-all border border-white/10"
                            >
                              {tpl}
                            </button>
                          ))}
                        </div>
                      </div>
                      <input
                        value={passwordPatternInline}
                        onChange={(e) => setPasswordPatternInline(e.target.value)}
                        placeholder="&lt;name&gt;sigmoid@123"
                        className="w-full bg-slate-900 border border-white/5 rounded-2xl p-5 text-white font-bold outline-none ring-1 ring-white/10 mb-4"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Data Stream (Full Name, Email, MemberID*)</label>
                      <textarea
                        value={onboardingData}
                        onChange={(e) => setOnboardingData(e.target.value)}
                        placeholder="John Wick, bobby@continental.com, EMP001&#10;Winston Scott, winston@continental.com, EMP002"
                        className="w-full h-48 bg-slate-900 border border-white/5 rounded-3xl p-6 text-white font-mono text-sm resize-none outline-none ring-1 ring-white/10"
                      />
                      <p className="text-[9px] text-slate-600 mt-2 italic">* CSV Format: One entity per line. MemberID is optional but recommended.</p>
                    </div>
                    <button
                      disabled={!nodeDetails?.id || !onboardingData.trim() || processing}
                      onClick={async () => {
                        setProcessing(true);
                        try {
                          const lines = onboardingData.split('\n').filter(l => l.includes(','));
                          const users = lines.map(line => {
                            const [name, email, memberId] = line.split(',').map(s => s.trim());
                            return { full_name: name, email, role: 'Member', member_id: memberId || null };
                          });
                          await ApiService.bulkAddUsers(nodeDetails.id, users, passwordPatternInline);
                          toast('success', `${users.length} entities integrated into protocol`);
                          setOnboardingData('');
                          setView('dashboard');
                          fetchData();
                        } catch (err: any) { toast('error', err.message); }
                        finally { setProcessing(false); }
                      }}
                      className="w-full bg-indigo-600 text-white py-5 rounded-[2rem] font-black uppercase tracking-widest shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-3 disabled:opacity-30"
                    >
                      {processing ? <Loader2 className="animate-spin" /> : <BadgeCheck />}
                      Execute Integration Flow
                    </button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Target Group</label>
                        <select
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold text-sm outline-none"
                          value={nodeDetails?.id || ''}
                          onChange={(e) => {
                            const id = parseInt(e.target.value);
                            const g = findGroupInTree(id, tree);
                            setNodeDetails({ type: 'GROUP', id, name: g?.name || 'Unknown' });
                          }}
                        >
                          <option value="">Select Target...</option>
                          {allPossibleGroups.map(g => (
                            <option key={g.id} value={g.id}>{g.context ? `${g.context} / ` : ''}{g.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Corporate Role</label>
                        <input value={view === 'addMentor' ? 'Mentor' : 'Member'} disabled className="w-full bg-white/5 border border-white/5 rounded-2xl p-4 text-slate-500 font-bold text-sm" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Full Legal Name</label>
                        <input
                          value={individualUser.fullName}
                          onChange={e => setIndividualUser({ ...individualUser, fullName: e.target.value })}
                          placeholder="e.g. Satoshi Nakamoto"
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Registry Email</label>
                        <input
                          value={individualUser.email}
                          onChange={e => setIndividualUser({ ...individualUser, email: e.target.value })}
                          placeholder="satoshi@bitcoin.org"
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Strategic Entity ID (Optional)</label>
                        <input
                          value={individualUser.memberId}
                          onChange={e => setIndividualUser({ ...individualUser, memberId: e.target.value })}
                          placeholder="e.g. EMP-99"
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-[0.2em]">Identity Password (Override)</label>
                        <input
                          type="password"
                          value={individualUser.password}
                          onChange={e => setIndividualUser({ ...individualUser, password: e.target.value })}
                          placeholder="••••••••"
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none ring-1 ring-brand-primary/20"
                        />
                      </div>
                    </div>
                    <button
                      disabled={!nodeDetails?.id || !individualUser.fullName || !individualUser.email || processing}
                      onClick={async () => {
                        setProcessing(true);
                        try {
                          await ApiService.bulkAddUsers(nodeDetails.id, [{
                            full_name: individualUser.fullName,
                            email: individualUser.email,
                            role: view === 'addMentor' ? 'Mentor' : 'Member',
                            member_id: individualUser.memberId,
                            password: individualUser.password // Explicitly passing override password
                          }]);
                          toast('success', 'Individual entity registered successfully');
                          setIndividualUser({ fullName: '', email: '', role: 'Member', password: '', memberId: '' });
                          setView('dashboard');
                          fetchData();
                        } catch (err: any) { toast('error', err.message); }
                        finally { setProcessing(false); }
                      }}
                      className="w-full bg-emerald-600 text-white py-5 rounded-[2rem] font-black uppercase tracking-widest shadow-xl shadow-emerald-600/30 flex items-center justify-center gap-3 disabled:opacity-30"
                    >
                      {processing ? <Loader2 className="animate-spin" /> : <Check />}
                      Register Entity
                    </button>
                  </div>
                )}
              </motion.div>
</>
  );
}
