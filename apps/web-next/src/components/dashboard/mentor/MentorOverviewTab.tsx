'use client';
/* Extracted verbatim from MentorDashboard.tsx (5b decomposition). */
/* eslint-disable @typescript-eslint/no-unused-vars */
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
import ApiService, { AIResponseEnvelope } from '../../../services/ApiService';
import { useToast } from '../../ui/Toast';
import AssignmentCreationModal from '.././AssignmentCreationModal';
import CodingQuestionModal from '.././CodingQuestionModal';
import BankCreationModal from '.././BankCreationModal';
import UserIntelPanel from '.././UserIntelPanel';
import MemberAssignmentHistory from '../../mentor/MemberAssignmentHistory';

import type { MentorCtx } from './types';

export default function MentorOverviewTab({ ctx }: { ctx: MentorCtx }) {
  const { loading, groups, selectedGroupId, setSelectedGroupId, groupStats,
    mentorStats, recentAttempts, students, searchQuery, setSearchQuery,
    showAssignmentModal, setShowAssignmentModal, showCodingModal,
    setShowCodingModal, showBankModal, setShowBankModal, showAtlasModal,
    setShowAtlasModal, selectedStudent, setSelectedStudent, activeMainTab,
    setActiveMainTab, courses, showReviewModal, setShowReviewModal,
    groupAiSummary, loadingSummary, selectedStudentHistory,
    setSelectedStudentHistory, ktInbox, fetchPendingReviews, fetchGroups,
    fetchGroupDetails, user, onBack, onViewPremium, toast } = ctx;
  return (
<>
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
</>
  );
}
