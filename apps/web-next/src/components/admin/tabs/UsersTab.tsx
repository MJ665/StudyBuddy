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

export default function UsersTab({ ctx }: { ctx: AdminTabCtx }) {
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
                key="users"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                {/* User Filtering */}
                <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
                  {selectedUserIds.size > 0 ? (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex items-center gap-4 p-3 bg-brand-primary/10 border border-brand-primary/20 rounded-2xl"
                    >
                      <span className="text-[10px] font-black text-brand-primary uppercase tracking-widest px-4 border-r border-brand-primary/20">
                        {selectedUserIds.size} Selected
                      </span>
                      <div className="flex gap-2">
                        <button
                          disabled={bulkProcessing}
                          onClick={() => handleBulkAction('activate')}
                          className="px-4 py-2 bg-emerald-500/10 text-emerald-400 text-[9px] font-black uppercase tracking-widest rounded-xl hover:bg-emerald-500 hover:text-white transition-all flex items-center gap-2"
                        >
                          {bulkProcessing ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                          Activate
                        </button>
                        <button
                          disabled={bulkProcessing}
                          onClick={() => handleBulkAction('deactivate')}
                          className="px-4 py-2 bg-amber-500/10 text-amber-400 text-[9px] font-black uppercase tracking-widest rounded-xl hover:bg-amber-500 hover:text-white transition-all flex items-center gap-2"
                        >
                          {bulkProcessing ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
                          Deactivate
                        </button>
                      </div>
                      <button
                        onClick={() => setSelectedUserIds(new Set())}
                        className="ml-4 text-on-surface-variant hover:text-white"
                      >
                        <X size={16} />
                      </button>
                    </motion.div>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-3">
                    <Filter size={14} className="text-on-surface-variant" />

                    <select
                      value={roleFilter}
                      onChange={(e) => setRoleFilter(e.target.value)}
                      className="bg-surface-dim border border-surface-bright rounded-xl px-4 py-3 text-[10px] text-white font-bold outline-none cursor-pointer"
                    >
                      <option value="All">All Roles</option>
                      <option value="Member">Member</option>
                      <option value="Mentor">Mentor</option>
                      <option value="LDAdmin">LDAdmin</option>
                      <option value="GroupAdmin">GroupAdmin</option>
                    </select>

                    <select
                      value={verticalFilter}
                      onChange={(e) => {
                        setVerticalFilter(e.target.value);
                        setBatchFilter('All');
                        setGroupFilter('All');
                      }}
                      className="bg-surface-dim border border-surface-bright rounded-xl px-4 py-3 text-[10px] text-white font-bold outline-none cursor-pointer"
                    >
                      <option value="All">All Verticals</option>
                      {[...new Set(users.map(u => u.vertical_name).filter(Boolean))].map((v: any) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>

                    <select
                      value={batchFilter}
                      disabled={verticalFilter === 'All'}
                      onChange={(e) => {
                        setBatchFilter(e.target.value);
                        setGroupFilter('All');
                      }}
                      className="bg-surface-dim border border-surface-bright rounded-xl px-4 py-3 text-[10px] text-white font-bold outline-none cursor-pointer disabled:opacity-30"
                    >
                      <option value="All">All Batches</option>
                      {[...new Set(users.filter(u => u.vertical_name === verticalFilter).map(u => u.batch_name).filter(Boolean))].map((b: any) => (
                        <option key={b} value={b}>{b}</option>
                      ))}
                    </select>

                    <select
                      value={groupFilter}
                      disabled={batchFilter === 'All'}
                      onChange={(e) => setGroupFilter(e.target.value)}
                      className="bg-surface-dim border border-surface-bright rounded-xl px-4 py-3 text-[10px] text-white font-bold outline-none cursor-pointer disabled:opacity-30"
                    >
                      <option value="All">All Groups</option>
                      {[...new Set(users.filter(u => u.batch_name === batchFilter).map(u => u.group_name).filter(Boolean))].map((g: any) => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => {
                      const csvContent = "data:text/csv;charset=utf-8,"
                        + "Name,Email,Role,Group,Batch\n"
                        + filteredUsers.map(u => `${u.full_name},${u.email},${u.role},${u.group_name},${u.batch_name}`).join("\n");
                      const encodedUri = encodeURI(csvContent);
                      const link = document.createElement("a");
                      link.setAttribute("href", encodedUri);
                      link.setAttribute("download", "user_registry.csv");
                      document.body.appendChild(link);
                      link.click();
                    }}
                    className="flex items-center gap-2 px-5 py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl text-[10px] font-black uppercase tracking-widest border border-white/5 transition-all"
                  >
                    <Download size={14} /> Export Registry
                  </button>
                </div>

                <div className="bg-surface-dim/40 border border-surface-bright rounded-[2.5rem] overflow-hidden">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-surface-bright bg-surface-bright/5">
                        <th className="px-8 py-5">
                          <input
                            type="checkbox"
                            className="w-4 h-4 rounded-md border-white/10 bg-white/5 text-brand-primary focus:ring-brand-primary cursor-pointer"
                            checked={filteredUsers.length > 0 && selectedUserIds.size === filteredUsers.length}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedUserIds(new Set(filteredUsers.map(u => u.id)));
                              } else {
                                setSelectedUserIds(new Set());
                              }
                            }}
                          />
                        </th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">UID / MemberID</th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Identity Information</th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Auth Level</th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Node Hierarchy</th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Registry Epoch</th>
                        <th className="px-8 py-5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant text-right">Strategic Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-bright/30">
                      {filteredUsers.map(u => (
                        <tr key={u.id} className={`hover:bg-white/5 transition-colors group ${selectedUserIds.has(u.id) ? 'bg-brand-primary/5' : ''}`}>
                          <td className="px-8 py-6">
                            <input
                              type="checkbox"
                              className="w-4 h-4 rounded-md border-white/10 bg-white/5 text-brand-primary focus:ring-brand-primary cursor-pointer"
                              checked={selectedUserIds.has(u.id)}
                              onChange={(e) => {
                                const next = new Set(selectedUserIds);
                                if (e.target.checked) next.add(u.id);
                                else next.delete(u.id);
                                setSelectedUserIds(next);
                              }}
                            />
                          </td>
                          <td className="px-8 py-6">
                            <div className="flex flex-col">
                              <span className="text-[10px] font-mono font-black text-brand-primary/60">#{u.id}</span>
                              {u.member_id && <span className="text-[8px] font-sans font-black text-indigo-400 uppercase tracking-tighter">{u.member_id}</span>}
                            </div>
                          </td>
                          <td className="px-8 py-6">
                            <div className="flex items-center gap-4">
                              <div className="w-10 h-10 rounded-2xl bg-brand-primary/10 flex items-center justify-center text-brand-primary font-black">
                                {u.full_name?.[0] || 'U'}
                              </div>
                              <div>
                                <p className="text-sm font-black text-white">{u.full_name}</p>
                                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">{u.email}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-8 py-6">
                            <span className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${u.role === 'LDAdmin' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' :
                              u.role === 'Mentor' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                                'bg-indigo-500/10 border-indigo-500/20 text-indigo-400'
                              }`}>
                              {u.role}
                            </span>
                          </td>
                          <td className="px-8 py-6">
                            <div className="flex flex-col gap-1">
                              <p className="text-[10px] text-white font-black uppercase tracking-widest">
                                {u.group_name || 'Global'}
                              </p>
                              <p className="text-[8px] text-slate-600 font-bold uppercase tracking-tight italic">
                                {u.batch_name ? `${u.batch_name} Sector` : 'Autonomous Operator'}
                              </p>
                            </div>
                          </td>
                          <td className="px-8 py-6">
                            <div className="flex flex-col gap-1 text-on-surface-variant">
                              <p className="text-[10px] font-black uppercase tracking-widest">{new Date(u.created_at).toLocaleDateString()}</p>
                              <p className="text-[8px] font-bold opacity-60 uppercase">{new Date(u.created_at).toLocaleTimeString()}</p>
                            </div>
                          </td>
                          <td className="px-8 py-6 text-right">
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => {
                                  setPromoteId(u.id.toString());
                                  toast('success', `UID #${u.id} loaded into Role Override tool`);
                                  // Scroll to the tool if on mobile/small screen, though sidebar is usually visible
                                  document.getElementById('role-override-tool')?.scrollIntoView({ behavior: 'smooth' });
                                }}
                                className="px-4 py-2 rounded-lg bg-indigo-500/10 text-indigo-400 text-[9px] font-black uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-all hover:bg-indigo-500 hover:text-white border border-indigo-500/20"
                              >
                                Promote
                              </button>
                              {user?.role === 'LDAdmin' && (
                                <button
                                  onClick={() => handleEmergencyReset(u)}
                                  className="px-4 py-2 rounded-lg bg-rose-500/10 text-rose-400 text-[9px] font-black uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-all hover:bg-rose-500 hover:text-white border border-rose-500/20"
                                >
                                  Reset Pass
                                </button>
                              )}
                              <button
                                onClick={() => setSelectedUserDetails(u)}
                                className="px-4 py-2 rounded-lg bg-surface-bright/10 text-brand-primary text-[9px] font-black uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-all hover:bg-brand-primary hover:text-slate-950"
                              >
                                Sync Intel
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredUsers.length === 0 && (
                    <div className="p-20 text-center">
                      <p className="text-xs text-on-surface-variant font-black uppercase tracking-widest italic">No entities detected in this sector.</p>
                    </div>
                  )}
                </div>
              </motion.div>
</>
  );
}
