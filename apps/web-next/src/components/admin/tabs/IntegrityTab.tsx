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

export default function IntegrityTab({ ctx }: { ctx: AdminTabCtx }) {
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
                key="integrity"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <DataIntegrityDashboard />
              </motion.div>
</>
  );
}
