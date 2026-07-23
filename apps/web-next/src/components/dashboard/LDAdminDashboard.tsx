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
import AssignmentCreationModal from './AssignmentCreationModal';
import CourseEnrollmentModal from './CourseEnrollmentModal';
import CodingQuestionModal from './CodingQuestionModal';
import BankCreationModal from './BankCreationModal';
import NotificationCenter from '../common/NotificationCenter';
import { ComparisonChart, CompositeHealthGauge, EngagementDecayWidget, PerformanceDistributionChart, LeaderboardTable } from './AnalyticsCharts';
import UserIntelPanel from './UserIntelPanel';
import QuestionManagement from './QuestionManagement';
import QuestionReportUI from '../admin/QuestionReportUI';
import DataIntegrityDashboard from './DataIntegrityDashboard';
import SystemHealthMonitor from './SystemHealthMonitor';
import { StatCard, OrgNode, DeptNode, SystemHealthPanel, PerformanceMetricGrid } from '../admin/AdminWidgets';
import { ResourceModal, DeleteModal, BulkAddModal, UserDetailsModal, CreationModal } from '../admin/AdminModals';
import { getAllGroups, findGroupInTree, getAllBatches } from './admin/adminTree';
import LDAdminModals from '../admin/LDAdminModals';
import { AuditLogTable, EmailLogTable, QuestionReportTable, SecurityPulse } from '../admin/AdminTables';
import CurriculumTab from '../admin/tabs/CurriculumTab';
import CodingTab from '../admin/tabs/CodingTab';
import AuditTab from '../admin/tabs/AuditTab';
import AnalyticsTab from '../admin/tabs/AnalyticsTab';
import ReportsTab from '../admin/tabs/ReportsTab';
import InventoryTab from '../admin/tabs/InventoryTab';
import TelemetryTab from '../admin/tabs/TelemetryTab';
import IntegrityTab from '../admin/tabs/IntegrityTab';
import HierarchyTab from '../admin/tabs/HierarchyTab';
import UsersTab from '../admin/tabs/UsersTab';
import AdminOnboardingOverlay from '../admin/AdminOnboardingOverlay';

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

export default function LDAdminDashboard({
  user,
  onLogout,
  onViewReport,
  onViewPremium,
  isOpsView = false
}: {
  user: any,
  onLogout?: () => void,
  onViewReport?: (batchId: number) => void,
  onViewPremium?: (slugOrId: string | number) => void,
  isOpsView?: boolean
}) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);

  // Section 6: Empty state for unassigned Mentors
  if (user?.role === 'Mentor' && (!user?.assigned_groups || user.assigned_groups.length === 0) && user?.group_id == null) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-8">
        <div className="relative mb-8">
          <ShieldAlert size={64} className="text-amber-500 animate-pulse" />
          <div className="absolute -inset-4 bg-amber-500/20 blur-2xl rounded-full -z-10" />
        </div>
        <h1 className="text-2xl font-black text-white uppercase tracking-tighter mb-2">No Cohort Assigned</h1>
        <p className="text-on-surface-variant text-sm max-w-md text-center font-medium">
          Strategic oversight requires an active assignment. Please contact your LDAdmin to link your profile to a group.
        </p>
        <button
          onClick={() => onLogout?.()}
          className="mt-8 px-8 py-4 bg-indigo-600 rounded-xl text-white font-black text-xs uppercase tracking-widest hover:bg-indigo-500 transition-all active:scale-95 shadow-lg shadow-indigo-500/20"
        >
          Logout & Reset
        </button>
      </div>
    );
  }
  const [tree, setTree] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [showAddModal, setShowAddModal] = useState<any>(null); // { type: 'Dept', parentId: 1 }
  const [showEditModal, setShowEditModal] = useState<any>(null); // { type: 'Dept', id: 1, name: '...' }
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<any>(null); // { type: 'Dept', id: 1, name: '...' }
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [taskData, setTaskData] = useState<any[]>([]);

  type AdminTab = 'Hierarchy' | 'Users' | 'Curriculum' | 'Coding' | 'Audit' | 'Analytics' | 'Reports' | 'Inventory' | 'Integrity' | 'Telemetry';
  const ADMIN_TABS: AdminTab[] = ['Hierarchy', 'Users', 'Curriculum', 'Coding', 'Audit', 'Analytics', 'Reports', 'Inventory', 'Integrity', 'Telemetry'];
  // Tabs are URL-addressable (/admin?tab=Users) so admin views deep-link,
  // survive refresh, and appear in browser history (Phase 4).
  const [activeTab, setActiveTabState] = useState<AdminTab>(() => {
    if (typeof window !== 'undefined') {
      const t = new URLSearchParams(window.location.search).get('tab') as AdminTab | null;
      if (t && ADMIN_TABS.includes(t)) return t;
    }
    return 'Hierarchy';
  });
  const setActiveTab = (t: AdminTab) => {
    setActiveTabState(t);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', t);
      window.history.replaceState({}, '', url.toString());
    }
  };
  const [users, setUsers] = useState<any[]>([]);
  const [userSearch, setUserSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('All');
  const [verticalFilter, setVerticalFilter] = useState('All');
  const [batchFilter, setBatchFilter] = useState('All');
  const [groupFilter, setGroupFilter] = useState('All');
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [showCourseModal, setShowCourseModal] = useState(false);
  const [showCodingModal, setShowCodingModal] = useState(false);
  const [showBankModal, setShowBankModal] = useState(false);
  const [courses, setCourses] = useState<any[]>([]);
  const [selectedUserDetails, setSelectedUserDetails] = useState<any>(null);
  const [view, setView] = useState<'dashboard' | 'onboarding' | 'addUser' | 'addMentor'>('dashboard');
  const [nodeDetails, setNodeDetails] = useState<any>(null);
  const [onboardingData, setOnboardingData] = useState('');
  const [processing, setProcessing] = useState(false);
  const [individualUser, setIndividualUser] = useState({ fullName: '', email: '', role: 'Member', password: '', memberId: '' });
  const [promoteId, setPromoteId] = useState('');
  const [promoteRole, setPromoteRole] = useState('Mentor');

  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [bulkProcessing, setBulkProcessing] = useState(false);

  // Curriculum & Coding State
  const [newCourseName, setNewCourseName] = useState('');
  const [addingCourse, setAddingCourse] = useState(false);
  const [bankCourseId, setBankCourseId] = useState<number | ''>('');
  const [auditSubTab, setAuditSubTab] = useState<'Audit' | 'Email'>('Audit');

  // Analytics & Batch AI Insights
  const [selectedAnalyticsBatch, setSelectedAnalyticsBatch] = useState<number | null>(null);
  const [batchIntel, setBatchIntel] = useState<any>(null);
  const [fetchingInsights, setFetchingInsights] = useState(false);
  const [executiveSummary, setExecutiveSummary] = useState<string | null>(null);

  const [globalInsights, setGlobalInsights] = useState<any[]>([]);
  const [fetchingGlobal, setFetchingGlobal] = useState(false);
  const [globalSummary, setGlobalSummary] = useState<string | null>(null);

  const [codingQuestions, setCodingQuestions] = useState<any[]>([]);
  const [addingCoding, setAddingCoding] = useState(false);
  const [codingLoading, setCodingLoading] = useState(false);
  const [codingFields, setCodingFields] = useState({
    title: '',
    description: '',
    initial_code: '',
    sample_solution: '',
    course_id: 0
  });

  const allPossibleGroups = getAllGroups(tree);
  const allPossibleBatches = getAllBatches(tree);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const isMentor = user?.role === 'Mentor';
      // Section 6: Resolve Mentor group context
      const mentorGroups = user?.assigned_groups || (user?.group_id ? [user.group_id] : []);
      const mentorGroupId = isMentor ? mentorGroups[0] : null;

      const [treeRes, statsRes, usersRes, coursesRes] = await Promise.all([
        ApiService.getOrgTree(),
        isMentor && mentorGroupId
          ? ApiService.getGroupHealth(mentorGroupId)
          : (user?.role === 'LDAdmin' ? ApiService.getLndStats() : Promise.resolve(null)),
        ApiService.getUsers(isMentor && mentorGroupId ? { group_id: mentorGroupId } : {}),
        ApiService.getCourses(isMentor && mentorGroupId ? mentorGroupId : (user?.group_id || 0))
      ]);
      setTree(treeRes);
      setStats(statsRes);
      setUsers(Array.isArray(usersRes) ? usersRes : (usersRes?.items || []));
      setCourses(Array.isArray(coursesRes) ? coursesRes : (coursesRes?.items || coursesRes || []));
    } catch (err: any) {
      toast('error', 'Failed to sync administrative state');
    } finally {
      setLoading(false);
    }
  };

  const toggleNode = (id: string) => {
    const next = new Set(expandedNodes);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpandedNodes(next);
  };

  const handleAdd = async (name: string) => {
    const { type, parentId } = showAddModal;
    try {
      if (type === 'Org') await ApiService.createOrg({ name });
      else if (type === 'Dept') await ApiService.createDept({ name, org_id: parentId });
      else if (type === 'Vertical') await ApiService.createVertical({ name, dept_id: parentId });
      else if (type === 'Batch') await ApiService.createBatch({ name, vertical_id: parentId });
      else if (type === 'Group') await ApiService.createGroupV3({ name, batch_id: parentId });

      toast('success', `${type} initialized in registry`);
      setShowAddModal(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    }
  };

  const handleUpdateResource = async (name: string) => {
    if (!showEditModal) return;
    const { type, id } = showEditModal;
    setProcessing(true);
    try {
      if (type === 'Org') await ApiService.updateOrg(id, { name });
      else if (type === 'Dept') await ApiService.updateDept(id, { name });
      else if (type === 'Vertical') await ApiService.updateVertical(id, { name });
      else if (type === 'Batch') await ApiService.updateBatch(id, { name });
      else if (type === 'Group') await ApiService.updateGroup(id, { name });

      toast('success', `${type} identity updated`);
      setShowEditModal(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleDeleteResource = async () => {
    if (!showDeleteConfirm) return;
    const { type, id } = showDeleteConfirm;
    setProcessing(true);
    try {
      if (type === 'Org') await ApiService.deleteOrg(id);
      else if (type === 'Dept') await ApiService.deleteDept(id);
      else if (type === 'Vertical') await ApiService.deleteVertical(id);
      else if (type === 'Batch') await ApiService.deleteBatch(id);
      else if (type === 'Group') await ApiService.deleteGroup(id);

      toast('success', `${type} purged from registry`);
      setShowDeleteConfirm(null);
      fetchData();
    } catch (err: any) {
      toast('error', err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleAddCourse = async () => {
    if (!newCourseName.trim()) return;
    try {
      await ApiService.createCourse({ name: newCourseName });
      toast('success', 'New course integrated into curriculum');
      setNewCourseName('');
      setAddingCourse(false);
      fetchData();
    } catch (err: any) { toast('error', err.message); }
  };

  const handleCreateCodingQuestion = async () => {
    if (!codingFields.title || !codingFields.course_id) {
      toast('error', 'Incomplete challenge parameters');
      return;
    }
    setCodingLoading(true);
    try {
      await ApiService.createCodingQuestion(codingFields);
      toast('success', 'Coding challenge published to registry');
      setAddingCoding(false);
      setCodingFields({ title: '', description: '', initial_code: '', sample_solution: '', course_id: 0 });
      fetchCodingQuestions();
    } catch (err: any) { toast('error', err.message); }
    finally { setCodingLoading(false); }
  };

  const fetchCodingQuestions = async () => {
    try {
      const res = await ApiService.request('/code/questions');
      setCodingQuestions(Array.isArray(res) ? res : (res?.items || []));
    } catch { /* silent */ }
  };

  useEffect(() => {
    if (activeTab === 'Coding') fetchCodingQuestions();
  }, [activeTab]);

  const handleFetchBatchInsights = async (refresh: boolean = false) => {
    if (!selectedAnalyticsBatch) {
      toast('error', 'Select a batch target for AI synthesis.');
      return;
    }
    setFetchingInsights(true);
    try {
      const [intelRes, summaryRes, fullMetricsRes] = await Promise.all([
        ApiService.getBatchAiInsights(selectedAnalyticsBatch, refresh),
        ApiService.getBatchExecutiveSummary(selectedAnalyticsBatch, refresh),
        ApiService.getBatchIntel(selectedAnalyticsBatch, refresh)
      ]) as [any, ExecutiveSummary, any];
      setBatchIntel({ ...intelRes, fullMetrics: fullMetricsRes });
      setExecutiveSummary(summaryRes.summary || null);
      toast('success', refresh ? 'Cohort Strategy Force-Synchronized' : 'Executive AI Intelligence Synced');
    } catch (err: any) {
      toast('error', 'Synthesis failed: Neural pipeline congested.');
    } finally {
      setFetchingInsights(false);
    }
  };

  const handleFetchGlobalInsights = async (refresh: boolean = false) => {
    setFetchingGlobal(true);
    try {
      const [aiRes, fullMetricsRes] = await Promise.all([
        ApiService.getAnalyticsAiInsights(refresh),
        ApiService.getGlobalIntel(refresh)
      ]);
      setGlobalInsights(aiRes.insights || []);
      setGlobalSummary(aiRes.summary || null);
      // We'll store global metrics in a new state
      setGlobalMetrics(fullMetricsRes);
      toast('success', refresh ? 'Global Intelligence Force-Synchronized' : 'Organization Intelligence Synced');
    } catch (err: any) {
      toast('error', 'Global synthesis failure: Neural pipeline congested.');
    } finally {
      setFetchingGlobal(false);
    }
  };

  const [globalMetrics, setGlobalMetrics] = useState<any>(null);

  const handleBulkAction = async (action: 'activate' | 'deactivate') => {
    setBulkProcessing(true);
    try {
      await ApiService.bulkAdminAction(Array.from(selectedUserIds), action as any);
      toast('success', `Bulk operation completed: ${selectedUserIds.size} users updated.`);
      setSelectedUserIds(new Set());
      fetchData();
    } catch (err: any) {
      toast('error', `Bulk action failed: ${err.message}`);
    } finally {
      setBulkProcessing(false);
    }
  };

  if (loading && tree.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-brand-primary"></div>
      </div>
    );
  }

  const handleEmergencyReset = async (u: any) => {
    const newPass = window.prompt(`Emergency Password Reset for ${u.full_name}\n\nEnter new password (min 8 chars):`);
    if (!newPass) return;
    if (newPass.length < 8) {
      toast('error', 'Password must be at least 8 characters long.');
      return;
    }
    setProcessing(true);
    try {
      await ApiService.adminResetPassword(u.id, newPass);
      toast('success', `Password for ${u.full_name} has been reset.`);
    } catch (err: any) {
      toast('error', `Failed to reset password: ${err.message}`);
    } finally {
      setProcessing(false);
    }
  };

  const filteredUsers = users.filter(u => {
    const trimmedSearch = userSearch.trim().toLowerCase();
    const matchesSearch = (u.full_name || '').toLowerCase().trim().includes(trimmedSearch) ||
      (u.email || '').toLowerCase().trim().includes(trimmedSearch);
    const matchesRole = roleFilter === 'All' || u.role === roleFilter;
    const matchesVertical = verticalFilter === 'All' || u.vertical_name === verticalFilter;
    const matchesBatch = batchFilter === 'All' || u.batch_name === batchFilter;
    const matchesGroup = groupFilter === 'All' || u.group_name === groupFilter;
    return matchesSearch && matchesRole && matchesVertical && matchesBatch && matchesGroup;
  });

  // Context handed to the extracted tab components (5b decomposition).
  const adminCtx = { toast, loading,
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
    onViewPremium };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-10 bg-slate-950">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-brand-primary mb-2">
            {isOpsView ? <Activity size={20} /> : <ShieldCheck size={20} />}
            <span className="font-black uppercase tracking-[0.2em] text-[10px]">
              {isOpsView ? 'Operations Protocol' : 'L&D Executive Protocol'}
            </span>
          </div>
          <h1 className="text-4xl font-black text-white">
            {isOpsView ? 'Ops Center' : 'Administration'}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowAddModal({ type: 'Org' })}
            className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-2xl text-xs font-black uppercase tracking-widest border border-white/5 transition-all flex items-center gap-2"
          >
            <Building2 size={16} /> New Organization
          </button>
          <button onClick={() => setView('onboarding')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${view === 'onboarding' ? 'bg-brand-primary text-slate-950 shadow-lg shadow-brand-primary/20' : 'bg-slate-800 text-slate-400 hover:text-white'}`}>
            <Upload size={16} /> Bulk Integration
          </button>
          <button
            onClick={() => {
              setNodeDetails({ type: 'ORG_ADMIN', id: 0, name: 'System Admin' });
              setView('addUser');
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${view === 'addUser' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
          >
            <Plus size={16} /> Add User
          </button>
          <div className="ml-2 pl-4 border-l border-white/10">
            <NotificationCenter />
          </div>
        </div>
      </header>

      {/* Action Bar */}
      <div className="flex gap-4 mb-8">
        {[
          { icon: <Database size={16} />, label: 'Provision Bank', onClick: () => setShowBankModal(true) },
          { icon: <Plus size={16} />, label: 'Create Coding', onClick: () => setShowCodingModal(true) },
          {
            icon: <Database size={16} />, label: 'Seed Daily', onClick: async () => {
              toast('info', "Initializing Synchonicity Protocol...");
              try {
                await ApiService.seedDailyChallenges();
                toast('success', "Challenges generated successfully");
              } catch (err: any) { toast('error', err.message); }
            }
          },
          { icon: <Target size={16} />, label: 'Direct Mandate', onClick: () => setShowAssignmentModal(true) },
          { icon: <BookmarkPlus size={16} />, label: 'Mandate Course', onClick: () => setShowCourseModal(true) },
          {
            icon: <Terminal size={16} />, label: 'Task Monitor', onClick: async () => {
              toast('info', "Fetching System Task Status...");
              try {
                const res = await ApiService.getAllTaskStatus();
                setTaskData(res || []);
                setShowTaskModal(true);
              } catch (err: any) { toast('error', err.message); }
            }
          },
        ].map((action, i) => (
          <div
            key={i}
            className="flex-1 p-5 rounded-3xl bg-surface-container border border-surface-bright flex items-center gap-4 group transition-all text-left"
          >
            <div
              onClick={action.onClick}
              className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center text-brand-primary group-hover:scale-110 transition-transform cursor-pointer"
            >
              {action.icon}
            </div>
            <div onClick={action.onClick} className="cursor-pointer">
              <p className="text-sm font-black text-white">{action.label}</p>
              <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Resource creation suite</p>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison Analytics */}
      <div className="mb-10 p-8 bg-surface-container border border-surface-bright rounded-[3rem]">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h3 className="text-xl font-black text-white">Comparative Performance Analytics</h3>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest mt-1">Cross-Sector Accuracy Benchmarks</p>
          </div>
          <div className="p-3 bg-brand-primary/10 rounded-2xl text-brand-primary">
            <TrendingUp size={24} />
          </div>
        </div>
        <ComparisonChart
          data={stats?.recent_trends || []}
          type="bar"
          dataKey="value"
          nameKey="label"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        <div className="lg:col-span-2 space-y-10">
          {/* Tabs & Global Search (Section 13) */}
          <div className="flex flex-col md:flex-row gap-6 items-center justify-between">
            <div className="flex bg-surface-container p-1 rounded-2xl w-fit border border-surface-bright flex-wrap">
              {['Hierarchy', 'Users', 'Curriculum', 'Coding', 'Inventory', 'Audit', 'Analytics', 'Reports', 'Integrity', 'Telemetry'].map((tab: any) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab as any)}
                  className={`px-8 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${activeTab === tab ? 'bg-brand-primary text-slate-950 shadow-lg' : 'text-on-surface-variant hover:text-white'
                    }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {(activeTab === 'Hierarchy' || activeTab === 'Users') && (
              <div className="relative w-full md:w-80">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={16} />
                <input
                  type="text"
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  placeholder="Search Strategic Nodes or Identities..."
                  className="w-full bg-surface-dim border border-surface-bright rounded-xl pl-10 pr-4 py-3 text-xs text-white focus:ring-1 focus:ring-brand-primary outline-none shadow-inner"
                />
              </div>
            )}
          </div>

          <AnimatePresence mode="wait">
            {view !== 'dashboard' ? (
              <AdminOnboardingOverlay ctx={adminCtx} />
            ) : activeTab === 'Curriculum' ? (
              <CurriculumTab ctx={adminCtx} />
            ) : activeTab === 'Coding' ? (
              <CodingTab ctx={adminCtx} />
            ) : activeTab === 'Audit' ? (
              <AuditTab ctx={adminCtx} />
            ) : activeTab === 'Analytics' ? (
              <AnalyticsTab ctx={adminCtx} />
            ) : activeTab === 'Reports' ? (
              <ReportsTab ctx={adminCtx} />
            ) : activeTab === 'Inventory' ? (
              <InventoryTab ctx={adminCtx} />
            ) : activeTab === 'Telemetry' ? (
              <TelemetryTab ctx={adminCtx} />
            ) : activeTab === 'Integrity' ? (
              <IntegrityTab ctx={adminCtx} />
            ) : activeTab === 'Hierarchy' ? (
              <HierarchyTab ctx={adminCtx} />
            ) : (
              <UsersTab ctx={adminCtx} />
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-8">
          {/* Stats Cards */}
          <div className="grid grid-cols-1 gap-6">
            <StatCard
              icon={<Users size={20} />}
              label={user?.role === 'LDAdmin' ? "Managed Operators" : "Cohort Members"}
              value={stats?.active_users || 0}
              trend={stats?.uptake_trend || "Stable"}
              color="indigo"
            />
            <StatCard
              icon={<TrendingUp size={20} />}
              label={user?.role === 'LDAdmin' ? "Protocol Adoption" : "Learning Velocity"}
              value={`${stats?.system_uptake || 0}%`}
              trend="Optimal"
              color="emerald"
            />
          </div>

          <div className="bg-surface-container rounded-[2rem] border border-surface-bright p-8 shadow-2xl">
            <h4 className="text-xs font-black uppercase tracking-[0.2em] text-on-surface-variant mb-6 flex items-center gap-2">
              <Settings size={16} className="text-brand-primary" /> System Intelligence
            </h4>
            <SystemHealthPanel stats={stats} />
          </div>

          <div id="role-override-tool" className="bg-indigo-600/10 border border-indigo-500/30 rounded-[2rem] p-8 shadow-inner relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500 opacity-10 blur-3xl pointer-events-none" />
            <h4 className="text-xs font-black uppercase tracking-[0.2em] text-indigo-400 mb-6 flex items-center gap-2">
              <ShieldCheck size={16} /> Role Override
            </h4>
            <div className="flex flex-col gap-3">
              <input
                type="number"
                placeholder="Entity ID"
                value={promoteId}
                onChange={e => setPromoteId(e.target.value)}
                className="bg-slate-900 border border-indigo-500/20 rounded-xl px-4 py-3 text-xs text-white outline-none"
              />
              <select
                value={promoteRole}
                onChange={e => setPromoteRole(e.target.value)}
                className="bg-slate-900 border border-indigo-500/20 rounded-xl px-4 py-3 text-xs text-white outline-none"
              >
                <option>Mentor</option>
                {user?.role === 'LDAdmin' && (
                  <>
                    <option>LDAdmin</option>
                    <option>GroupAdmin</option>
                  </>
                )}
              </select>
              <button
                disabled={processing || !promoteId}
                onClick={async () => {
                  if (!promoteId) { toast('error', 'Entity ID is required'); return; }
                  const uid = parseInt(promoteId);
                  const targetUser = users.find(u => u.id === uid);
                  if (!targetUser) { toast('error', `No user found with ID ${promoteId}`); return; }
                  if (!window.confirm(`Are you sure you want to promote ${targetUser.full_name} to ${promoteRole}?`)) {
                    return;
                  }
                  setProcessing(true);
                  try {
                    const res = await ApiService.updateUserRole(uid, promoteRole);
                    toast('success', res.message || `${targetUser.full_name} → ${promoteRole}`);
                    setPromoteId('');
                    await fetchData(); // Re-fetch org tree after promotion
                  } catch (err: any) {
                    // PROMOTE-001: Show real backend error instead of always showing success
                    toast('error', err.message || `Promotion failed — ${targetUser.full_name} may not be eligible for ${promoteRole}`);
                  } finally {
                    setProcessing(false);
                  }
                }}
                className="w-full bg-indigo-600 text-white p-3 rounded-xl font-black text-[10px] uppercase tracking-widest hover:bg-indigo-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {processing ? <><Loader2 size={12} className="animate-spin" /> Processing...</> : 'Execute Promotion'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <LDAdminModals ctx={adminCtx} />
    </div>
  );
}



