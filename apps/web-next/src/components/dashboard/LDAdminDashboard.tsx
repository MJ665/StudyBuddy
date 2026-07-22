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
  if (user?.role === 'Mentor' && (!user?.assigned_groups || user.assigned_groups.length === 0) && !user?.group_id) {
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
  const [passwordPatternInline, setPasswordPatternInline] = useState('<name>sigmoid@123');
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

  const getAllGroups = (nodes: any[]): any[] => {
    let groups: any[] = [];
    nodes?.forEach(node => {
      // 1. Check if node is a Group itself
      if (node.id && !node.departments && !node.verticals && !node.batches && !node.groups) {
        // This case might only happen if the tree is flat, but we handle it just in case
      }

      // 2. Check for explicit groups array at this level
      if (node.groups && Array.isArray(node.groups)) {
        node.groups.forEach((g: any) => groups.push({ ...g, context: node.name }));
      }

      // 3. Recursive traversal through all possible container fields
      const containers = ['departments', 'verticals', 'batches'];
      containers.forEach(containerKey => {
        if (node[containerKey] && Array.isArray(node[containerKey])) {
          groups = [...groups, ...getAllGroups(node[containerKey])];
        }
      });
    });
    return groups;
  };

  const findGroupInTree = (id: number, nodes: any[]): any | null => {
    for (const node of nodes) {
      if (node.groups) {
        const found = node.groups.find((g: any) => g.id === id);
        if (found) return found;
      }
      const children = node.departments || node.verticals || node.batches;
      if (children) {
        const found: any = findGroupInTree(id, children);
        if (found) return found;
      }
    }
    return null;
  };

  const allPossibleGroups = getAllGroups(tree);

  const getAllBatches = (nodes: any[]): any[] => {
    let batches: any[] = [];
    nodes?.forEach(node => {
      if (node.batches && Array.isArray(node.batches)) {
        node.batches.forEach((b: any) => batches.push({ ...b, context: node.name }));
      }
      const containers = ['departments', 'verticals'];
      containers.forEach(containerKey => {
        if (node[containerKey] && Array.isArray(node[containerKey])) {
          batches = [...batches, ...getAllBatches(node[containerKey])];
        }
      });
    });
    return batches;
  };

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
            ) : activeTab === 'Curriculum' ? (
              <motion.div
                key="curriculum"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-8"
              >
                {/* Courses Management */}
                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <div className="flex justify-between items-center mb-8">
                    <div>
                      <h3 className="text-2xl font-black text-white">Dynamic Curriculum</h3>
                      <p className="text-[10px] text-brand-primary font-black uppercase tracking-[0.3em] mt-1">Course Catalog & Strategy</p>
                    </div>
                    <button
                      onClick={() => setAddingCourse(!addingCourse)}
                      className="px-6 py-3 bg-brand-primary text-slate-950 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-primary/90 transition-all shadow-lg shadow-brand-primary/20 flex items-center gap-2"
                    >
                      <Plus size={14} /> {addingCourse ? 'Cancel' : 'New Course'}
                    </button>
                  </div>

                  {addingCourse && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-6 bg-white/5 border border-white/10 rounded-3xl mb-8 flex gap-4 items-end"
                    >
                      <div className="flex-1">
                        <label className="block text-[10px] font-black uppercase text-slate-500 mb-2 tracking-widest">Course Designation</label>
                        <input
                          value={newCourseName}
                          onChange={e => setNewCourseName(e.target.value)}
                          className="w-full bg-slate-900 border border-white/5 rounded-2xl p-4 text-white font-bold outline-none ring-1 ring-white/10 focus:ring-brand-primary/30"
                          placeholder="e.g. Advanced Distributed Systems"
                        />
                      </div>
                      <button
                        onClick={handleAddCourse}
                        className="bg-brand-primary text-slate-950 font-black uppercase tracking-widest text-[10px] py-4 px-8 rounded-2xl shadow-xl shadow-brand-primary/20"
                      >
                        Initialize
                      </button>
                    </motion.div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {courses.map(c => (
                      <div key={c.id} className="p-6 bg-slate-900/50 border border-white/5 rounded-[2.5rem] flex items-center justify-between group hover:border-brand-primary/30 transition-all">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-brand-primary font-black text-xs">
                            {c.name?.[0]}
                          </div>
                          <span className="text-sm font-black text-white">{c.name}</span>
                        </div>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all">
                          <button className="p-2 text-slate-500 hover:text-white"><Settings size={14} /></button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>


              </motion.div>
            ) : activeTab === 'Coding' ? (
              <motion.div
                key="coding"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-8"
              >
                {/* Coding Challenge Creator */}
                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <div className="flex justify-between items-center mb-8">
                    <div>
                      <h3 className="text-2xl font-black text-white">Coding Lab Management</h3>
                      <p className="text-[10px] text-emerald-400 font-black uppercase tracking-[0.3em] mt-1">Algorithmic Challenge Registry</p>
                    </div>
                    <button
                      onClick={() => setShowCodingModal(true)}
                      className="px-6 py-3 bg-emerald-600 text-white rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500 transition-all shadow-lg shadow-emerald-600/20 flex items-center gap-2"
                    >
                      <Plus size={14} /> New Challenge
                    </button>
                  </div>


                  {/* Coding Registry Table */}
                  <div className="bg-slate-900/50 border border-white/5 rounded-[3rem] overflow-hidden">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-white/5">
                          <th className="px-8 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Challenge Title</th>
                          <th className="px-8 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Course Sector</th>
                          <th className="px-8 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">System ID</th>
                          <th className="px-8 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {(Array.isArray(codingQuestions) ? codingQuestions : []).map(q => (
                          <tr key={q.id} className="group hover:bg-white/5 transition-all">
                            <td className="px-8 py-6">
                              <p className="text-sm font-black text-white">{q.title}</p>
                              <p className="text-[10px] text-slate-500 truncate max-w-xs">{q.description?.substring(0, 50)}...</p>
                            </td>
                            <td className="px-8 py-6">
                              <span className="px-3 py-1 rounded-lg bg-white/5 text-slate-400 text-[10px] font-black uppercase border border-white/5">
                                {courses.find(c => c.id === q.course_id)?.name || 'General Registry'}
                              </span>
                            </td>
                            <td className="px-8 py-6 font-mono text-[10px] font-black text-brand-primary/60">
                              #{q.id}
                            </td>
                            <td className="px-8 py-6 text-right">
                              <button className="p-2 text-slate-500 hover:text-white transition-all"><Settings size={16} /></button>
                            </td>
                          </tr>
                        ))}
                        {(Array.isArray(codingQuestions) ? codingQuestions : []).length === 0 && (
                          <tr>
                            <td colSpan={4} className="px-8 py-20 text-center">
                              <p className="text-[10px] font-black text-slate-600 uppercase tracking-widest italic">No coding challenges found in current registry.</p>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </motion.div>
            ) : activeTab === 'Audit' ? (
              <motion.div
                key="audit"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-8">
                      <div>
                        <h3 className="text-2xl font-black text-white">Governance & Auditing</h3>
                        <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mt-1">Immutable Immutable Audit Trail (AUD-205)</p>
                      </div>
                      <div className="flex bg-slate-900 p-1 rounded-xl border border-white/5">
                        <button
                          onClick={() => setAuditSubTab('Audit')}
                          className={`px-4 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${auditSubTab === 'Audit' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}
                        >
                          Actions
                        </button>
                        <button
                          onClick={() => setAuditSubTab('Email')}
                          className={`px-4 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${auditSubTab === 'Email' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}
                        >
                          Mail Logs
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => ApiService.export_global_activity()}
                        className="flex items-center gap-2 px-6 py-3 bg-brand-primary/20 text-brand-primary rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-primary/30 transition-all border border-brand-primary/30 shadow-lg shadow-brand-primary/10"
                      >
                        <Download size={16} /> Download Global Activity
                      </button>
                      <div className="p-3 bg-indigo-500/10 rounded-2xl text-indigo-400">
                        <Clock size={20} />
                      </div>
                    </div>
                  </div>

                  <SecurityPulse />

                  {auditSubTab === 'Audit' ? <AuditLogTable /> : <EmailLogTable />}
                </div>
              </motion.div>
            ) : activeTab === 'Analytics' ? (
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
            ) : activeTab === 'Reports' ? (
              <motion.div
                key="reports"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="bg-slate-900 border border-white/5 rounded-[3rem] overflow-hidden p-8"
              >
                <div className="flex justify-between items-center mb-8">
                  <div>
                    <h3 className="text-2xl font-black text-white">Content Quality Audit</h3>
                    <p className="text-[10px] text-rose-400 font-black uppercase tracking-[0.3em] mt-1">Question Reporting & Remediation</p>
                  </div>
                  <div className="p-3 bg-rose-500/10 rounded-2xl text-rose-400">
                    <ShieldAlert size={20} />
                  </div>
                </div>
                <QuestionReportUI />
              </motion.div>
            ) : activeTab === 'Inventory' ? (
              <motion.div
                key="inventory"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <div className="bg-surface-container border border-surface-bright rounded-[3rem] p-8">
                  <div className="flex items-center justify-between mb-8">
                    <div>
                      <h3 className="text-2xl font-black text-white">Registry Oversight</h3>
                      <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mt-1">Global Question & Challenge Inventory</p>
                    </div>
                    <div className="p-3 bg-indigo-500/10 rounded-2xl text-indigo-400">
                      <Database size={20} />
                    </div>
                  </div>
                  <QuestionManagement user={user} />
                </div>
              </motion.div>
            ) : activeTab === 'Telemetry' ? (
              <motion.div
                key="telemetry"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <SystemHealthMonitor />
              </motion.div>
            ) : activeTab === 'Integrity' ? (
              <motion.div
                key="integrity"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="space-y-6"
              >
                <DataIntegrityDashboard />
              </motion.div>
            ) : activeTab === 'Hierarchy' ? (
              <motion.div
                key="hierarchy"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="space-y-4"
              >
                {filterTree(tree, userSearch).map(org => (
                  <OrgNode
                    onEdit={setShowEditModal}
                    onDelete={setShowDeleteConfirm}
                    key={org.id}
                    org={org}
                    expanded={expandedNodes.has(`org-${org.id}`)}
                    onToggle={() => toggleNode(`org-${org.id}`)}
                    onAdd={setShowAddModal}
                    onAction={(action: string, id: number, name: string, targetType?: string) => {
                      setNodeDetails({ action, id, name, targetType });
                      if (action === 'MEMBER_ADD') setView('addUser');
                      else if (action === 'MENTOR_ADD') setView('addMentor');
                      else if (action === 'MANDATE') setShowAssignmentModal(true);
                    }}
                    expandedNodes={expandedNodes}
                    toggleNode={toggleNode}
                    onViewReport={onViewReport}
                  />
                ))}
              </motion.div>
            ) : (
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
                      {[...new Set(users.map(u => u.vertical_name).filter(Boolean))].map(v => (
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
                      {[...new Set(users.filter(u => u.vertical_name === verticalFilter).map(u => u.batch_name).filter(Boolean))].map(b => (
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
                      {[...new Set(users.filter(u => u.batch_name === batchFilter).map(u => u.group_name).filter(Boolean))].map(g => (
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

      <AnimatePresence>
        {showAddModal && showAddModal.type === 'BulkUser' ? (
          <BulkAddModal
            onClose={() => setShowAddModal(null)}
            tree={tree}
            currentUser={user}
            onSubmit={async (groupId: number, userList: any[]) => {
              try {
                await ApiService.bulkAddUsers(groupId, userList);
                toast('success', `Onboarded ${userList.length} users successfully`);
                setShowAddModal(null);
                fetchData();
              } catch (err: any) {
                toast('error', err.message);
              }
            }}
          />
        ) : showAddModal && (
          <CreationModal
            type={showAddModal.type}
            onClose={() => setShowAddModal(null)}
            onSubmit={handleAdd}
          />
        )}
        {showAssignmentModal && (
          <AssignmentCreationModal
            initialTargetType={nodeDetails?.action === 'MANDATE' ? (nodeDetails.targetType as any) : undefined}
            initialTargetId={nodeDetails?.action === 'MANDATE' ? nodeDetails.id : undefined}
            onClose={() => setShowAssignmentModal(false)}
            onCreated={() => { setShowAssignmentModal(false); fetchData(); }}
          />
        )}
        {showCodingModal && (
          <CodingQuestionModal
            user={user}
            courses={courses}
            onClose={() => setShowCodingModal(false)}
            onCreated={() => { setShowCodingModal(false); fetchData(); }}
          />
        )}
        {showEditModal && (
          <ResourceModal
            type={showEditModal.type}
            initialName={showEditModal.name}
            onClose={() => setShowEditModal(null)}
            onSubmit={handleUpdateResource}
            mode="EDIT"
          />
        )}
        {showDeleteConfirm && (
          <DeleteModal
            type={showDeleteConfirm.type}
            name={showDeleteConfirm.name}
            onClose={() => setShowDeleteConfirm(null)}
            onConfirm={handleDeleteResource}
            processing={processing}
          />
        )}
        {showBankModal && (
          <BankCreationModal
            user={user}
            courses={courses}
            onClose={() => setShowBankModal(false)}
            onCreated={() => { setShowBankModal(false); fetchData(); }}
          />
        )}
        {selectedUserDetails && (
          <UserIntelPanel
            userId={selectedUserDetails.id}
            onClose={() => setSelectedUserDetails(null)}
            onViewPremium={onViewPremium}
          />
        )}
        {showCourseModal && (
          <CourseEnrollmentModal
            onClose={() => setShowCourseModal(false)}
            onEnrolled={() => { setShowCourseModal(false); fetchData(); }}
          />
        )}
        {showTaskModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setShowTaskModal(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-4xl bg-surface-container border border-surface-bright rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]"
            >
              <div className="p-6 border-b border-surface-bright flex justify-between items-center bg-slate-900/50">
                <div>
                  <h3 className="text-xl font-black text-white flex items-center gap-2">
                    <Terminal className="text-indigo-400" size={24} /> System Task Monitor
                  </h3>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mt-1">
                    Live Background Job Telemetry
                  </p>
                </div>
                <button onClick={() => setShowTaskModal(false)} className="text-slate-500 hover:text-white transition-colors">
                  <X size={24} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 bg-slate-950">
                {taskData.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                    <CheckCircle size={48} className="mb-4 opacity-20" />
                    <p className="font-bold text-sm uppercase tracking-widest">No active or recent tasks found.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {taskData.map((task, i) => (
                      <div key={i} className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest ${
                              task.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                              task.status === 'FAILED' ? 'bg-rose-500/20 text-rose-400' :
                              task.status === 'RUNNING' ? 'bg-indigo-500/20 text-indigo-400' :
                              'bg-amber-500/20 text-amber-400'
                            }`}>
                              {task.status || 'UNKNOWN'}
                            </span>
                            <span className="text-sm font-bold text-white">{task.task_name}</span>
                          </div>
                          {task.error_message && (
                            <p className="text-xs text-rose-400 font-mono bg-rose-500/5 p-2 rounded-lg border border-rose-500/10 mb-2">
                              {task.error_message}
                            </p>
                          )}
                          <div className="flex items-center gap-4 text-[10px] text-slate-500 font-mono">
                            <span>Started: {new Date(task.started_at).toLocaleString()}</span>
                            {task.completed_at && <span>Completed: {new Date(task.completed_at).toLocaleString()}</span>}
                            <span>Target ID: {task.target_id || 'N/A'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

