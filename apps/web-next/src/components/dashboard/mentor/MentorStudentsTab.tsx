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

export default function MentorStudentsTab({ ctx }: { ctx: MentorCtx }) {
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
{selectedStudentHistory && (
               <MemberAssignmentHistory 
                 student={selectedStudentHistory} 
                 onBack={() => setSelectedStudentHistory(null)} 
               />
)}
{!selectedStudentHistory && (
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
</>
  );
}
