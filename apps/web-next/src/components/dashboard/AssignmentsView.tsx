import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ClipboardList, 
  Calendar, 
  CheckCircle2, 
  Clock, 
  ChevronRight, 
  AlertCircle,
  BrainCircuit,
  Code,
  Lock,
  ArrowLeft,
  Loader2
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import AssignmentDetailModal from './AssignmentDetailModal';

interface Assignment {
  assignment_id: number;
  bank_id: number | null;
  coding_question_id: number | null;
  assignment_type: 'quiz' | 'coding';
  bank_name: string;
  due_date: string;
  instructions: string;
  is_completed: boolean;
  status: 'not_started' | 'in_progress' | 'passed' | 'failed' | 'completed';
  score: number | null;
  attempts_used: number;
  max_attempts: number | null;
  passing_score_percent: number | null;
  lock_after_due: boolean;
}

interface AssignmentsViewProps {
  user: any;
  onStartQuiz: (bank: any, maxQuestions: number) => void;
  onStartCoding: (question: any) => void;
  onBack: () => void;
}

export default function AssignmentsView({ user, onStartQuiz, onStartCoding, onBack }: AssignmentsViewProps) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('active');
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);

  useEffect(() => {
    fetchAssignments();
  }, []);

  const fetchAssignments = async () => {
    try {
      const data = await ApiService.getMyAssignments();
      setAssignments(data);
    } catch (err) {
      console.error("Failed to load assignments", err);
    } finally {
      setLoading(false);
    }
  };

  const filteredAssignments = assignments.filter(a => {
    if (filter === 'all') return true;
    if (filter === 'active') return !a.is_completed;
    if (filter === 'completed') return a.is_completed;
    return true;
  });

  const isOverdue = (date: string) => {
    if (!date) return false;
    return new Date(date) < new Date();
  };

  const handleStartAssignment = (asgn: Assignment) => {
    setSelectedAssignment(null);
    if (asgn.assignment_type === 'quiz') {
      onStartQuiz({ id: asgn.bank_id, name: asgn.bank_name }, 50);
    } else {
      onStartCoding({ id: asgn.coding_question_id, title: asgn.bank_name });
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8 font-plus-jakarta">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-12">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-6">
             <button onClick={onBack} className="p-3 bg-slate-900 border border-white/5 rounded-2xl text-slate-500 hover:text-white transition-all">
                <ArrowLeft size={20} />
             </button>
             <div>
               <h1 className="text-4xl font-black text-white mb-2 tracking-tight flex items-center gap-4">
                 <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl text-indigo-400">
                   <ClipboardList size={32} />
                 </div>
                 Mandatory Assignments
               </h1>
               <p className="text-slate-500 font-bold uppercase tracking-[0.2em] text-[10px]">Strategic Learning Directives & Compliance</p>
             </div>
          </div>
          
          <div className="flex bg-slate-900/50 p-1 rounded-2xl border border-white/5">
            {(['active', 'completed', 'all'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
                  filter === f 
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 space-y-4">
            <Loader2 className="animate-spin text-indigo-500" size={48} />
            <p className="text-slate-500 font-black uppercase tracking-widest text-xs">Synchronizing Directives...</p>
          </div>
        ) : filteredAssignments.length === 0 ? (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/30 border border-dashed border-white/10 rounded-[3rem] p-24 text-center"
          >
            <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mx-auto mb-6 text-slate-600">
               <CheckCircle2 size={40} />
            </div>
            <h3 className="text-2xl font-black text-white mb-2">Registry Clear</h3>
            <p className="text-slate-500 font-medium">No pending assignments found in your current sector.</p>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <AnimatePresence mode="popLayout">
              {filteredAssignments.map((asgn, idx) => {
                const overdue = isOverdue(asgn.due_date);
                const canAttempt = !asgn.is_completed && (!overdue || !asgn.lock_after_due);

                return (
                  <motion.div
                    key={asgn.assignment_id}
                    layout
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ delay: idx * 0.05 }}
                    onClick={() => setSelectedAssignment(asgn)}
                    className={`group bg-slate-900/40 backdrop-blur-xl border ${
                      asgn.is_completed ? 'border-emerald-500/20' : overdue ? 'border-rose-500/20' : 'border-white/5'
                    } rounded-[2.5rem] p-8 hover:bg-slate-900/60 transition-all relative overflow-hidden cursor-pointer shadow-2xl`}
                  >
                    {/* Status Badge */}
                    <div className="flex justify-between items-start mb-6">
                      <div className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-2 ${
                        asgn.is_completed ? 'bg-emerald-500/10 text-emerald-400' :
                        overdue ? 'bg-rose-500/10 text-rose-400' : 'bg-indigo-500/10 text-indigo-400'
                      }`}>
                        {asgn.is_completed ? <CheckCircle2 size={12} /> : overdue ? <AlertCircle size={12} /> : <Clock size={12} />}
                        {asgn.is_completed ? 'Completed' : overdue ? 'Overdue' : 'Active'}
                      </div>
                      
                      <div className="flex gap-2">
                         <div className="p-2 bg-slate-950 rounded-xl text-slate-500">
                            {asgn.assignment_type === 'quiz' ? <BrainCircuit size={16} /> : <Code size={16} />}
                         </div>
                      </div>
                    </div>

                    <h3 className="text-xl font-black text-white mb-2 group-hover:text-indigo-400 transition-colors line-clamp-1">{asgn.bank_name}</h3>
                    <p className="text-slate-500 text-sm mb-6 line-clamp-2 font-medium leading-relaxed">{asgn.instructions || "No specific instructions provided for this directive."}</p>

                    <div className="grid grid-cols-2 gap-4 mb-8">
                       <div className="bg-slate-950/50 p-4 rounded-2xl border border-white/5">
                          <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1">Due Date</p>
                          <p className={`text-xs font-bold ${overdue ? 'text-rose-400' : 'text-slate-300'}`}>
                             {asgn.due_date ? new Date(asgn.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'No Deadline'}
                          </p>
                       </div>
                       <div className="bg-slate-950/50 p-4 rounded-2xl border border-white/5">
                          <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1">Attempts</p>
                          <p className="text-xs font-bold text-slate-300">
                             {asgn.attempts_used} / {asgn.max_attempts || '∞'}
                          </p>
                       </div>
                    </div>

                    {asgn.is_completed ? (
                      <div className="flex items-center justify-between p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl">
                         <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-black text-xs">
                               {asgn.score}%
                            </div>
                            <p className="text-xs font-bold text-emerald-500/80 uppercase tracking-widest">Protocol Passed</p>
                         </div>
                         <CheckCircle2 size={20} className="text-emerald-500" />
                      </div>
                    ) : !canAttempt ? (
                      <div className="flex items-center gap-3 p-4 bg-rose-500/5 border border-rose-500/10 rounded-2xl text-rose-500">
                         <Lock size={18} />
                         <p className="text-xs font-black uppercase tracking-widest">Access Locked (Overdue)</p>
                      </div>
                    ) : (
                      <button 
                        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-black uppercase tracking-[0.2em] text-[10px] transition-all shadow-xl shadow-indigo-600/20 flex items-center justify-center gap-2"
                      >
                         Open Detailed View <ChevronRight size={14} />
                      </button>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>

      <AnimatePresence>
        {selectedAssignment && (
          <AssignmentDetailModal 
            assignment={selectedAssignment}
            onClose={() => setSelectedAssignment(null)}
            onStart={handleStartAssignment}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
