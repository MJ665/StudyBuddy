import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Users, 
  ChevronRight, 
  MessageSquare, 
  CheckCircle2, 
  Clock, 
  Search, 
  Filter,
  TrendingUp,
  Award,
  BookOpen,
  PieChart as PieChartIcon,
  UserCheck,
  Plus,
  Code,
  Code2,
  Trophy,
  X,
  Loader2,
  Sparkles,
  Brain,
  RefreshCw,
  LayoutDashboard
} from 'lucide-react';
import ApiService, { AIResponseEnvelope } from '../../services/ApiService';
import { useToast } from '../ui/Toast';
import AssignmentCreationModal from './AssignmentCreationModal';
import CodingQuestionModal from './CodingQuestionModal';
import BankCreationModal from './BankCreationModal';
import UserIntelPanel from './UserIntelPanel';
import MemberAssignmentHistory from '../mentor/MemberAssignmentHistory';

export default function MentorDashboard({ 
  user, 
  onBack,
  onViewPremium
}: { 
  user: any, 
  onBack: () => void,
  onViewPremium?: (slugOrId: string | number) => void
}) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [groupStats, setGroupStats] = useState<any>(null);
  const [mentorStats, setMentorStats] = useState<any>(null);
  const [recentAttempts, setRecentAttempts] = useState<any[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [showCodingModal, setShowCodingModal] = useState(false);
  const [showBankModal, setShowBankModal] = useState(false);
  const [showAtlasModal, setShowAtlasModal] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<any>(null);
  const [activeMainTab, setActiveMainTab] = useState<'DASHBOARD' | 'STUDENTS'>('DASHBOARD');
  const [courses, setCourses] = useState<any[]>([]);
  const [showReviewModal, setShowReviewModal] = useState<any>(null); // { id, type, user_name, score, total }
  const [groupAiSummary, setGroupAiSummary] = useState<string>('');
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [selectedStudentHistory, setSelectedStudentHistory] = useState<any>(null);
  const [ktInbox, setKtInbox] = useState<any[]>([]); // KT docs awaiting my review

  useEffect(() => {
    fetchGroups();
    fetchPendingReviews();
  }, []);

  useEffect(() => {
    if (selectedGroupId) {
      fetchGroupDetails(selectedGroupId);
    }
  }, [selectedGroupId]);

  const fetchPendingReviews = async () => {
    try {
      // Unified inbox (Phase 6): assessment reviews + KT docs in one call.
      const inbox = await ApiService.getUnifiedMentorInbox();
      setRecentAttempts(inbox.assessment || []);
      setKtInbox(inbox.kt_documents || []);
    } catch {
      // Fallback to the assessment-only queue if the inbox is unavailable.
      try {
        const pending = await ApiService.getPendingReviews();
        setRecentAttempts(pending);
      } catch (err) {
        console.error('Failed to fetch pending reviews', err);
      }
    }
  };

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const mentorGroups = await ApiService.getMentorGroups();
      setGroups(mentorGroups);
      if (mentorGroups.length > 0) setSelectedGroupId(mentorGroups[0].id);
      
      // Fetch courses for modals
      const coursesRes = await ApiService.getCourses(user.group_id);
      setCourses(coursesRes);
    } catch (err: any) {
      toast('error', `Failed to load mentor groups: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchGroupDetails = async (id: number, force: boolean = false) => {
    try {
      // Get health stats for participation/accuracy
      const health = await ApiService.getGroupHealth(id);
      setGroupStats(health);
      
      // Get mentor-specific analytics (performers, velocity, topics)
      const stats = await ApiService.getGroupStats(id);
      setMentorStats(stats);

      // Get students
      const studentList = await ApiService.getGroupStudents(id);
      setStudents(studentList);

      // Get AI Summary
      setLoadingSummary(true);
      try {
        const summaryRes = await ApiService.getGroupAiSummary(id, force) as AIResponseEnvelope;
        setGroupAiSummary(summaryRes.data?.summary || (summaryRes as any).summary);
      } catch (e) {
        setGroupAiSummary('AI analysis unavailable for this group.');
      } finally {
        setLoadingSummary(false);
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  if (loading && groups.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-brand-primary"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-8 py-10">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-indigo-400 mb-2">
            <UserCheck size={20} />
            <span className="font-black uppercase tracking-[0.2em] text-xs">Mentor Command Center</span>
          </div>
          <h1 className="text-4xl font-black text-white">Mentorship Hub</h1>
        </div>
        
        <div className="flex gap-4">
          <button 
            onClick={() => setShowBankModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-white/5 text-slate-300 rounded-2xl font-black border border-white/5 hover:bg-white/10 transition-all"
          >
            <BookOpen size={18} />
            <span>New Bank</span>
          </button>

          <button 
            onClick={() => setShowCodingModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-indigo-500/10 text-indigo-400 rounded-2xl font-black border border-indigo-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            <Code size={18} />
            <span>New Coding Lab</span>
          </button>
          
          <button 
            onClick={() => setShowAssignmentModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-brand-primary text-surface-dim rounded-2xl font-black shadow-xl shadow-brand-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            <Plus size={18} />
            <span>New Assignment</span>
          </button>
          
          {onBack && (
            <button 
              onClick={onBack}
              className="flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-2xl font-bold transition-all border border-slate-700 active:scale-95"
            >
              <BookOpen size={18} />
              <span>Exit Mentor Mode</span>
            </button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* ─── Assigned Groups Sidebar ──────────────────────── */}
        <div className="lg:col-span-1 space-y-4">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-2">My Assigned Groups</p>
          {groups.map(group => (
            <button
              key={group.id}
              onClick={() => setSelectedGroupId(group.id)}
              className={`w-full p-4 rounded-2xl border text-left transition-all ${
                selectedGroupId === group.id 
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/20' 
                  : 'bg-surface-container border-surface-bright text-slate-400 hover:border-indigo-500/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold">{group.name}</span>
                <ChevronRight size={16} className={selectedGroupId === group.id ? 'opacity-100' : 'opacity-0'} />
              </div>
              <p className={`text-[10px] uppercase font-black tracking-widest mt-1 ${selectedGroupId === group.id ? 'text-indigo-200' : 'text-slate-600'}`}>
                {group.batch_name || 'Active Batch'}
              </p>
            </button>
          ))}
          
          <div className="mt-8 p-6 bg-surface-container rounded-3xl border border-surface-bright">
             <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
                  <Award size={20} />
                </div>
                <p className="text-sm font-black text-white">Top Performers</p>
             </div>
             <div className="space-y-4">
                {(mentorStats?.top_performers || []).map((p: any) => (
                  <div key={p.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                       <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-400">{p.name.charAt(0)}</div>
                       <span className="text-xs text-slate-300 font-medium">{p.name}</span>
                    </div>
                    <span className="text-xs font-black text-emerald-400">{p.score}</span>
                  </div>
                ))}
                {(!mentorStats?.top_performers || mentorStats.top_performers.length === 0) && (
                  <p className="text-[10px] text-slate-500 italic">No data yet</p>
                )}
             </div>
          </div>
        </div>

        {/* ─── Main Content Panel ──────────────────────────── */}
        <div className="lg:col-span-3 space-y-6">
            <div className="flex gap-1 p-1 bg-surface-container rounded-2xl border border-surface-bright w-fit mb-4">
               <button 
                 onClick={() => setActiveMainTab('DASHBOARD')}
                 className={`px-6 py-2.5 rounded-xl font-black text-xs transition-all ${activeMainTab === 'DASHBOARD' ? 'bg-slate-900 text-indigo-400 border border-white/5 shadow-xl' : 'text-slate-500'}`}
               >DASHBOARD</button>
               <button 
                 onClick={() => setActiveMainTab('STUDENTS')}
                 className={`px-6 py-2.5 rounded-xl font-black text-xs transition-all ${activeMainTab === 'STUDENTS' ? 'bg-slate-900 text-indigo-400 border border-white/5 shadow-xl' : 'text-slate-500'}`}
               >STUDENTS</button>
            </div>

            {/* AI Group Insight Banner */}
            <div className="bg-gradient-to-br from-indigo-950/60 via-slate-900/60 to-surface-dim/40 p-10 rounded-[3rem] border border-white/5 relative overflow-hidden mb-8 shadow-2xl group">
               <div className="absolute -top-10 -right-10 w-64 h-64 bg-indigo-500/10 blur-[80px] pointer-events-none group-hover:bg-indigo-500/20 transition-all duration-1000" />
               <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3 text-indigo-400">
                    <Brain className="animate-pulse" size={24} />
                    <span className="text-[11px] font-black uppercase tracking-[0.4em]">Pedagogical Intelligence Pulse</span>
                  </div>
                  <button 
                    disabled={loadingSummary}
                    onClick={() => selectedGroupId && fetchGroupDetails(selectedGroupId, true)}
                    className="p-3 bg-white/5 hover:bg-white/10 text-slate-500 hover:text-white rounded-2xl border border-white/5 transition-all disabled:opacity-30 active:scale-95"
                    title="Recalibrate AI Vectors"
                  >
                    <RefreshCw size={18} className={loadingSummary ? 'animate-spin' : ''} />
                  </button>
               </div>
               
               {loadingSummary ? (
                 <div className="space-y-4">
                    <div className="h-4 bg-white/5 rounded-full w-3/4 animate-pulse" />
                    <div className="h-4 bg-white/5 rounded-full w-full animate-pulse" />
                    <div className="h-4 bg-white/5 rounded-full w-1/2 animate-pulse" />
                    <p className="text-slate-500 text-[10px] font-black uppercase tracking-widest mt-6 flex items-center gap-2">
                       <Loader2 size={12} className="animate-spin" /> Analyzing Group Performance Vectors...
                    </p>
                 </div>
               ) : (
                 <div className="relative z-10">
                    <p className="text-xl font-medium text-slate-200 leading-relaxed max-w-4xl italic mb-6">
                       "{groupAiSummary || 'Direct pedagogical intervention markers will appear here after student activity is detected.'}"
                    </p>
                    <div className="flex flex-wrap gap-4">
                       <div className="px-4 py-2 bg-indigo-500/10 border border-indigo-500/20 rounded-xl flex items-center gap-2">
                          <Sparkles size={14} className="text-indigo-400" />
                          <span className="text-[10px] font-black text-indigo-300 uppercase tracking-widest">AI Synthesis Active</span>
                       </div>
                       <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-2">
                          <TrendingUp size={14} className="text-emerald-400" />
                          <span className="text-[10px] font-black text-emerald-300 uppercase tracking-widest">Growth Vectors Mapped</span>
                       </div>
                    </div>
                 </div>
               )}
            </div>

            {activeMainTab === 'DASHBOARD' && (
              <div className="space-y-8">

           {/* Unified inbox: KT documents awaiting this mentor's review */}
           {ktInbox.length > 0 && (
             <div className="bg-surface-container p-6 rounded-3xl border border-amber-500/20">
               <div className="flex items-center justify-between mb-4">
                 <p className="text-xs font-black uppercase text-amber-400">
                   Knowledge Docs Awaiting Review ({ktInbox.length})
                 </p>
                 <a
                   href="/kt"
                   className="text-xs font-bold text-indigo-400 hover:text-indigo-300"
                 >
                   Open KT Workspace →
                 </a>
               </div>
               <div className="space-y-2">
                 {ktInbox.slice(0, 5).map((d: any) => (
                   <a
                     key={d.id}
                     href="/kt"
                     className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-white/5 hover:border-amber-500/30 transition-all"
                   >
                     <div>
                       <p className="text-sm font-bold text-white">{d.title}</p>
                       <p className="text-[10px] uppercase tracking-wider text-slate-500">
                         {d.doc_type || 'document'} · {d.status}
                       </p>
                     </div>
                     <span className="text-[10px] text-slate-500">
                       {d.submitted_at ? new Date(d.submitted_at).toLocaleDateString() : ''}
                     </span>
                   </a>
                 ))}
               </div>
             </div>
           )}

           {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-surface-container p-6 rounded-3xl border border-surface-bright">
                 <p className="text-xs font-black uppercase text-slate-500 mb-2">Participation</p>
                 <div className="flex items-end gap-3">
                    <p className="text-3xl font-black text-white">{groupStats?.participation_rate || 0}%</p>
                    <span className="text-emerald-400 text-xs font-bold mb-1">Live</span>
                 </div>
              </div>
              <div className="bg-surface-container p-6 rounded-3xl border border-surface-bright">
                 <p className="text-xs font-black uppercase text-slate-500 mb-2">Avg. Accuracy</p>
                 <div className="flex items-end gap-3">
                    <p className="text-3xl font-black text-white">
                      {groupStats?.health?.length 
                        ? (groupStats.health.reduce((acc: number, h: any) => acc + h.accuracy, 0) / groupStats.health.length).toFixed(1)
                        : '0'}%
                    </p>
                    <span className="text-slate-500 text-xs font-bold mb-1">Target: 80%</span>
                 </div>
              </div>
              <div className="bg-surface-container p-6 rounded-3xl border border-surface-bright">
                 <p className="text-xs font-black uppercase text-slate-500 mb-2">Pending Reviews</p>
                 <div className="flex items-end gap-3">
                    <p className="text-3xl font-black text-rose-400">{recentAttempts.length}</p>
                    <span className="text-rose-400/60 text-xs font-bold mb-1">Action Required</span>
                 </div>
              </div>
           </div>

           {/* Review Queue */}
           <div className="bg-surface-container rounded-3xl border border-surface-bright overflow-hidden shadow-xl">
              <div className="p-6 border-b border-surface-bright flex justify-between items-center">
                 <div className="flex items-center gap-3">
                    <MessageSquare size={20} className="text-indigo-400" />
                    <h3 className="text-lg font-black text-white">Review Queue</h3>
                 </div>
                 <div className="flex gap-3">
                    <div className="relative">
                       <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                       <input 
                         type="text" 
                         placeholder="Student name..." 
                         className="bg-surface-dim border border-surface-bright rounded-xl pl-8 pr-4 py-2 text-xs focus:outline-none"
                       />
                    </div>
                    <button className="p-2 bg-surface-dim border border-surface-bright rounded-xl text-slate-400">
                       <Filter size={16} />
                    </button>
                 </div>
              </div>

              <div className="divide-y divide-surface-bright/50">
                 {recentAttempts.length === 0 ? (
                    <div className="p-10 text-center">
                       <p className="text-slate-500 text-sm">No pending attempts in this group require review.</p>
                    </div>
                 ) : (
                   recentAttempts.map(attempt => (
                     <div key={`${attempt.type}-${attempt.id}`} className="p-6 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                        <div className="flex items-center gap-4">
                           <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sm font-bold text-indigo-400 border border-indigo-500/20 overflow-hidden">
                              {attempt.user_avatar ? (
                                <img src={attempt.user_avatar} alt="" className="w-full h-full object-cover" />
                              ) : (
                                attempt.user_name?.charAt(0) ?? "?"
                              )}
                           </div>
                           <div>
                              <p className="text-sm font-bold text-white leading-none mb-1">{attempt.user_name ?? "Unknown User"}</p>
                              <div className="flex items-center gap-3 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                                 <span className={`px-2 py-0.5 rounded ${attempt.type === 'coding' ? 'bg-amber-500/10 text-amber-400' : 'bg-blue-500/10 text-blue-400'}`}>
                                   {attempt.type}
                                 </span>
                                 <span className="flex items-center gap-1"><BookOpen size={10} /> {attempt.title ?? "Untitled"}</span>
                                 <span className="flex items-center gap-1"><Clock size={10} /> {attempt.attempted_at ? new Date(attempt.attempted_at).toLocaleDateString() : "Never"}</span>
                              </div>
                           </div>
                        </div>
                        <div className="flex items-center gap-4">
                           <div className="text-right">
                              <p className="text-sm font-black text-white">{attempt.score}/{attempt.total || 100}</p>
                              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Accuracy</p>
                           </div>
                           <div className="flex gap-2">
                              <button 
                                onClick={async () => {
                                  try {
                                    if (attempt.type === 'quiz') {
                                      await ApiService.reviewAttempt({
                                          attempt_id: attempt.id,
                                          attempt_type: 'quiz',
                                          is_reviewed: true,
                                          mentor_comment: 'Verified'
                                      });
                                    } else {
                                      await ApiService.verifyCodingAttempt(attempt.id);
                                    }
                                    toast('success', `Verified ${attempt.user_name}'s ${attempt.type} attempt`);
                                    fetchPendingReviews();
                                  } catch (err) {
                                    toast('error', 'Verification failed');
                                  }
                                }}
                                className="p-2.5 bg-emerald-600/10 text-emerald-500 hover:bg-emerald-600 hover:text-white rounded-xl transition-all border border-emerald-500/20"
                                title="Mark as Verified"
                              >
                                 <CheckCircle2 size={16} />
                              </button>
                              <button 
                                onClick={() => setShowReviewModal(attempt)}
                                className="p-2.5 bg-slate-800 text-slate-400 hover:text-white rounded-xl transition-all border border-slate-700 hover:border-slate-500"
                                title="Manual Override / Feedback"
                              >
                                 <Plus size={16} />
                              </button>
                              <button 
                                onClick={() => {
                                  setSelectedStudent({ id: attempt.user_id, full_name: attempt.user_name });
                                  setShowAtlasModal(true);
                                }}
                                className="p-2.5 bg-indigo-600/10 text-indigo-400 hover:bg-indigo-600 hover:text-white rounded-xl transition-all border border-indigo-500/20"
                                title="Sync AI Intel"
                              >
                                 <TrendingUp size={16} />
                              </button>
                           </div>
                        </div>
                     </div>
                   ))
                 )}
              </div>
           </div>

           {/* Topics for attention */}
            <div className="bg-surface-container rounded-3xl border border-surface-bright p-8">
              <div className="flex items-center gap-3 mb-8">
                 <PieChartIcon size={20} className="text-amber-400" />
                 <h3 className="text-lg font-black text-white">Curriculum Insights</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                 <div>
                    <p className="text-xs font-black uppercase text-slate-500 mb-4 tracking-widest">Topic Health (Weakest First)</p>
                    <div className="space-y-4">
                       {(mentorStats?.curriculum_insights || []).map((t: any) => (
                         <div key={t.topic} className="flex items-center justify-between p-3 bg-surface-dim rounded-2xl border border-surface-bright">
                            <div>
                               <p className="text-xs font-bold text-white">{t.topic}</p>
                               <p className={`text-[10px] font-black uppercase tracking-widest mt-0.5 ${
                                 t.accuracy < 60 ? 'text-rose-400' : 'text-amber-400'
                               }`}>{t.status}</p>
                            </div>
                            <div className="text-right">
                               <p className="text-sm font-black text-white">{t.accuracy}%</p>
                               <div className="w-16 h-1 bg-slate-800 rounded-full mt-1 overflow-hidden">
                                  <div className={`h-full ${
                                    t.accuracy < 60 ? 'bg-rose-500' : 'bg-amber-500'
                                  }`} style={{ width: `${t.accuracy}%` }} />
                               </div>
                            </div>
                         </div>
                       ))}
                       {(!mentorStats?.curriculum_insights || mentorStats.curriculum_insights.length === 0) && (
                         <p className="text-xs text-slate-500 italic">Insufficient data to generate insights.</p>
                       )}
                    </div>
                 </div>
                 <div>
                    <p className="text-xs font-black uppercase text-slate-500 mb-4 tracking-widest">Recent Activity Velocity</p>
                    <div className="space-y-4">
                       {(mentorStats?.assignment_velocity || []).map((v: any) => (
                         <div key={v.day} className="flex items-center justify-between p-3 bg-surface-dim rounded-2xl border border-surface-bright">
                            <div className="flex items-center gap-3">
                               <span className="text-xs font-bold text-white">{v.day}</span>
                            </div>
                            <div className="text-right">
                               <p className="text-xs font-black text-indigo-400">{v.count} Attempts</p>
                            </div>
                         </div>
                       ))}
                       {(!mentorStats?.assignment_velocity || mentorStats.assignment_velocity.length === 0) && (
                         <p className="text-xs text-slate-500 italic">No recent activity detected.</p>
                       )}
                    </div>
                 </div>
              </div>
            </div>
         </div>
      )}
            {activeMainTab === 'STUDENTS' && selectedStudentHistory && (
               <MemberAssignmentHistory 
                 student={selectedStudentHistory} 
                 onBack={() => setSelectedStudentHistory(null)} 
               />
            )}

            {activeMainTab === 'STUDENTS' && !selectedStudentHistory && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                 {students.map(student => (
                   <div key={student.id} className="p-6 bg-surface-container rounded-[2rem] border border-surface-bright group hover:border-indigo-500/30 transition-all">
                      <div className="flex items-center gap-4 mb-6">
                         <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 font-black text-xl">
                            {student.full_name?.charAt(0)}
                         </div>
                         <div>
                            <p className="font-black text-white">{student.full_name}</p>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{student.email_prefix}</p>
                         </div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-2 mb-6">
                          <div className="p-3 bg-white/5 rounded-2xl text-center border border-white/5 group-hover:border-indigo-500/20 transition-all">
                             <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">Acc.</p>
                             <p className="text-xs font-black text-emerald-400">{student.avg_accuracy}%</p>
                          </div>
                          <div className="p-3 bg-white/5 rounded-2xl text-center border border-white/5 group-hover:border-indigo-500/20 transition-all">
                             <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">Streak</p>
                             <p className="text-xs font-black text-amber-400">{student.streak_count}d</p>
                          </div>
                          <div className="p-3 bg-white/5 rounded-2xl text-center border border-white/5 group-hover:border-indigo-500/20 transition-all">
                             <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">Risk</p>
                             <p className={`text-xs font-black ${
                                student.risk_level?.includes('High') ? 'text-rose-400' :
                                student.risk_level?.includes('Medium') ? 'text-amber-400' :
                                'text-indigo-400'
                             }`}>{student.risk_level?.split(' ')[0] || 'Stable'}</p>
                          </div>
                       </div>
                      
                      <div className="flex gap-2">
                        <button 
                          onClick={() => {
                            setSelectedStudent(student);
                            setShowAtlasModal(true);
                          }}
                          className="flex-1 py-3 bg-indigo-600/10 text-indigo-400 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-indigo-600 hover:text-white transition-all"
                        >
                          Sync AI Intel
                        </button>
                        <button 
                          onClick={() => setSelectedStudentHistory(student)}
                          className="flex-1 py-3 bg-white/5 text-slate-400 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-white/10 hover:text-white transition-all border border-white/5"
                        >
                          View Portfolio
                        </button>
                      </div>
                   </div>
                 ))}
                 {students.length === 0 && (
                   <div className="col-span-full py-20 text-center">
                     <Users size={48} className="text-slate-800 mx-auto mb-4" />
                     <p className="text-slate-500">No students found in this group.</p>
                   </div>
                 )}
              </div>
            )}
         </div>
      </div>

      <AnimatePresence>
        {showAtlasModal && selectedStudent && (
          <UserIntelPanel 
            userId={selectedStudent.id}
            onClose={() => setShowAtlasModal(false)}
            onViewPremium={onViewPremium}
          />
        )}
        {showAssignmentModal && (
          <AssignmentCreationModal 
            user={user}
            onClose={() => setShowAssignmentModal(false)}
            onCreated={() => {
              setShowAssignmentModal(false);
              fetchGroups();
            }}
          />
        )}
        {showCodingModal && (
          <CodingQuestionModal 
            user={user}
            courses={courses}
            onClose={() => setShowCodingModal(false)}
            onCreated={() => {
              setShowCodingModal(false);
            }}
          />
        )}
        {showBankModal && (
          <BankCreationModal 
            user={user}
            courses={courses}
            onClose={() => setShowBankModal(false)}
            onCreated={() => {
              setShowBankModal(false);
              fetchGroups();
            }}
          />
        )}
        {showReviewModal && (
          <ReviewModal 
            attempt={showReviewModal}
            onClose={() => setShowReviewModal(null)}
            onReviewed={() => {
              setShowReviewModal(null);
              fetchPendingReviews();
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function ReviewModal({ attempt, onClose, onReviewed }: { attempt: any, onClose: () => void, onReviewed: () => void }) {
  const { toast } = useToast();
  const [comment, setComment] = useState('');
  const [overrideScore, setOverrideScore] = useState(attempt.score);
  const [processing, setProcessing] = useState(false);

  const handleSubmit = async () => {
    setProcessing(true);
    try {
      await ApiService.reviewAttempt({
        attempt_id: attempt.id,
        attempt_type: attempt.type,
        mentor_comment: comment,
        override_score: overrideScore !== attempt.score ? overrideScore : undefined,
        is_reviewed: true
      });
      toast('success', 'Artifact recalibrated and archived.');
      onReviewed();
    } catch (err: any) {
      toast('error', err.message || 'Failed to submit review');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-sm"
    >
      <motion.div 
        initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }}
        className="w-full max-w-3xl bg-slate-900 border border-white/5 rounded-[3rem] shadow-2xl overflow-hidden relative flex flex-col max-h-[90vh]"
      >
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-brand-primary" />
        
        <header className="p-8 pb-4 flex justify-between items-center shrink-0">
           <div>
              <h3 className="text-2xl font-black text-white">Manual Recalibration</h3>
              <p className="text-[10px] text-indigo-400 font-black uppercase tracking-[0.3em] mt-1">{attempt.type} Review / {attempt.user_name}</p>
           </div>
           <button onClick={onClose} className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all">
              <X size={20} className="text-slate-500 hover:text-white" />
           </button>
        </header>

        <div className="flex-1 overflow-y-auto p-8 pt-4 space-y-8 scrollbar-thin scrollbar-thumb-white/10">
          {/* Submission Details */}
          <div className="space-y-6">
            {attempt.type === 'coding' ? (
              <div className="space-y-4">
                <div className="bg-slate-950/50 rounded-3xl border border-white/5 overflow-hidden">
                  <div className="px-6 py-3 bg-white/5 border-b border-white/5 flex items-center justify-between">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Source Code Submission ({attempt.language})</span>
                    <Code2 size={14} className="text-indigo-400" />
                  </div>
                  <pre className="p-6 text-xs font-mono text-indigo-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96">
                    {attempt.submitted_code}
                  </pre>
                </div>

                {attempt.ai_feedback && (
                  <div className="bg-indigo-500/5 rounded-3xl border border-indigo-500/10 p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <Sparkles size={16} className="text-indigo-400" />
                      <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">AI Pedagogical Analysis</span>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed italic">
                      {attempt.ai_feedback}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between px-2">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Assessment Detail Registry</span>
                  <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Base Accuracy: {attempt.score}/{attempt.total}</span>
                </div>
                
                <div className="space-y-3">
                  {attempt.descriptive_answers?.map((ans: any, idx: number) => (
                    <div key={idx} className={`p-6 rounded-3xl border ${ans.is_correct ? 'bg-emerald-500/5 border-emerald-500/10' : 'bg-rose-500/5 border-rose-500/10'}`}>
                      <div className="flex items-start justify-between gap-4 mb-4">
                        <p className="text-sm font-bold text-white leading-relaxed">{idx + 1}. {ans.question_text}</p>
                        {ans.is_correct ? (
                          <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
                            <Trophy size={12} className="text-emerald-400" />
                          </div>
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-rose-500/20 flex items-center justify-center shrink-0">
                            <X size={12} className="text-rose-400" />
                          </div>
                        )}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-4 bg-black/20 rounded-2xl">
                          <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Student Answer</p>
                          <p className={`text-sm font-black ${ans.is_correct ? 'text-emerald-400' : 'text-rose-400'}`}>{ans.user_answer || 'No Answer'}</p>
                        </div>
                        {!ans.is_correct && (
                          <div className="p-4 bg-black/20 rounded-2xl">
                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Correct Reference</p>
                            <p className="text-sm font-black text-slate-300">{ans.correct_answer}</p>
                          </div>
                        )}
                      </div>
                      {ans.note && (
                        <div className="mt-4 pt-4 border-t border-white/5">
                          <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">User Reflection</p>
                          <p className="text-xs text-slate-400 italic font-medium leading-relaxed">"{ans.note}"</p>
                        </div>
                      )}
                    </div>
                  ))}
                  {(!attempt.descriptive_answers || attempt.descriptive_answers.length === 0) && (
                    <div className="py-20 text-center bg-white/5 rounded-[2rem] border border-dashed border-white/10">
                      <p className="text-slate-500 text-xs font-black uppercase tracking-widest">No detailed answer registry found</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-6 pt-8 border-t border-white/5">
             <div className="p-6 bg-slate-950/50 rounded-3xl border border-white/5">
                <div className="flex justify-between items-center mb-4">
                   <p className="text-[10px] font-black uppercase text-slate-500 tracking-widest">Suggested Score Recalibration</p>
                   <span className="px-3 py-1 bg-white/5 rounded-lg text-xs font-black text-white">{attempt.score} / {attempt.total}</span>
                </div>
                <div className="flex items-center gap-4">
                   <p className="text-xs font-bold text-slate-400">Override:</p>
                   <input 
                     type="number" 
                     min="0" 
                     max={attempt.total}
                     value={overrideScore}
                     onChange={e => setOverrideScore(parseFloat(e.target.value))}
                     className="flex-1 bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-white font-black text-center outline-none focus:ring-1 focus:ring-indigo-500"
                   />
                </div>
             </div>

             <div>
                <label className="block text-[10px] font-black uppercase text-slate-500 mb-3 tracking-widest">Mentor Pedagogical Feedback</label>
                <textarea 
                  value={comment}
                  onChange={e => setComment(e.target.value)}
                  placeholder="Direct feedback to student regarding their performance, strategy, or conceptual alignment..."
                  className="w-full h-32 bg-slate-950/50 border border-white/5 rounded-3xl p-6 text-white text-sm resize-none outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
                />
             </div>

             <button 
               disabled={processing}
               onClick={handleSubmit}
               className="w-full py-5 bg-indigo-600 text-white rounded-[2rem] font-black uppercase tracking-widest shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-3 active:scale-[0.98] transition-all disabled:opacity-50"
             >
                {processing ? <Loader2 className="animate-spin" /> : <div className="flex items-center gap-2"><Trophy size={18} /> Archive & Verify Submission</div>}
             </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
