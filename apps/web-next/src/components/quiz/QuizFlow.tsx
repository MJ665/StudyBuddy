import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import QuestionCard from './cards/QuestionCard';
import { 
  ChevronRight, 
  ChevronLeft, 
  Timer, 
  CheckCircle2, 
  AlertTriangle, 
  MessageSquare, 
  X, 
  Bookmark, 
  Save, 
  Info,
  LogOut,
  ChevronUp
} from 'lucide-react';
import { RichText } from '../common/RichText';
import CodeEditor from './CodeEditor';
import ApiService from '../../services/ApiService';
import QuestionDiscussions from './QuestionDiscussions';

const BEEP_WARNING_SECONDS = 5;

// Utility: play a short warning beep
function playBeep() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);
    oscillator.type = 'square';
    oscillator.frequency.value = 880;
    gainNode.gain.value = 0.3;
    oscillator.start();
    oscillator.stop(ctx.currentTime + 0.15);
  } catch (e) { /* ignore */ }
}

import { ConfirmationModal } from '../ui/ConfirmationModal';

export default function QuizFlow({ bank, questions, onFinish, onCancel, user }: any) {
  const DRAFT_KEY = `quiz_draft_${bank.id}_${user?.id || 'anon'}`;
  
  const loadDraft = () => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    return { answers: {}, notes: {}, currentIdx: 0, bookmarks: [] };
  };

  const initialDraft = loadDraft();
  const [currentIdx, setCurrentIdx] = useState(initialDraft.currentIdx || 0);
  const [answers, setAnswers] = useState<Record<number, string | string[]>>(initialDraft.answers || {});
  const [notes, setNotes] = useState<Record<number, string>>(initialDraft.notes || {});
  const [timeLeft, setTimeLeft] = useState(bank.time_per_question);
  const [quizStartTime] = useState<number>(Date.now());
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [direction, setDirection] = useState(1);
  const [showReportModal, setShowReportModal] = useState(false);
  const [showDiscussions, setShowDiscussions] = useState(false);
  const [bookmarks, setBookmarks] = useState<number[]>(initialDraft.bookmarks || []); // Now question IDs
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [lastSaved, setLastSaved] = useState<number | null>(null);
  
  // Report State
  const [reportReason, setReportReason] = useState('typo');
  const [reportComment, setReportComment] = useState('');
  const [reportSubmitting, setReportSubmitting] = useState(false);

  // Modal State
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  const currentQ = questions[currentIdx];
  const answeredCount = Object.keys(answers).length;

  // Sync bookmark status when question changes
  useEffect(() => {
    if (currentQ) {
      ApiService.getBookmarkStatus(currentQ.id)
        .then(res => setIsBookmarked(res.is_bookmarked))
        .catch(() => setIsBookmarked(bookmarks.includes(currentQ.id)));
    }
  }, [currentIdx, currentQ]);

  // Auto-save draft
  useEffect(() => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ answers, notes, currentIdx, bookmarks }));
    setLastSaved(Date.now());
  }, [answers, notes, currentIdx, bookmarks, DRAFT_KEY]);

  // Timer Logic
  useEffect(() => {
    let timer: any;
    if (bank.show_timer && timeLeft > 0) {
      if (timeLeft === BEEP_WARNING_SECONDS) playBeep();
      timer = setInterval(() => setTimeLeft((prev: number) => prev - 1), 1000);
    } else if (timeLeft === 0 && bank.show_timer) {
      handleNext();
    }
    return () => clearInterval(timer);
  }, [timeLeft, bank.show_timer, currentIdx]);

  const handleNext = () => {
    if (currentIdx < questions.length - 1) {
      setDirection(1);
      setCurrentIdx((prev: number) => prev + 1);
      setTimeLeft(bank.time_per_question);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      const unanswered = questions.filter((_: any, i: number) => {
        const a = answers[i];
        return a === undefined || a === '' || (Array.isArray(a) && a.length === 0);
      }).length;
      if (unanswered > 0) setConfirmSubmit(true);
      else finishQuiz();
    }
  };

  const handlePrev = () => {
    if (currentIdx > 0) {
      setDirection(-1);
      setCurrentIdx((prev: number) => prev - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const finishQuiz = async () => {
    setIsSubmitting(true);
    const timeTaken = Math.floor((Date.now() - quizStartTime) / 1000);
    localStorage.removeItem(DRAFT_KEY);
    try {
      const question_ids = questions.map((q: any) => q.id);
      // Multi-select answers are encoded as a JSON-array string so user_answers
      // stays List[str]; the backend decodes them before grading.
      const user_answers = questions.map((_: any, i: number) => {
        const a = answers[i];
        return Array.isArray(a) ? JSON.stringify(a) : (a || "");
      });
      const user_notes = questions.map((_: any, i: number) => notes[i] || "");

      const submitResult = await ApiService.submitAttempt({
        bank_id: bank.id,
        user_name: user?.full_name || "Anonymous",
        time_taken: timeTaken,
        question_ids,
        user_answers,
        user_notes,
        is_anonymous: isAnonymous
      });
      onFinish({ timeTaken, answers, notes, isAnonymous, submitResult });
    } catch (err: any) {
      console.error("Failed to submit attempt:", err);
      alert(`Submission failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitReport = async () => {
    if (!currentQ) return;
    setReportSubmitting(true);
    try {
      await ApiService.reportQuestion(currentQ.id, {
        issue_type: reportReason,
        description: reportComment
      });
      setShowReportModal(false);
      setReportComment('');
      // Using a custom modal or simple alert for now as per user preference if not specified
      alert('Thank you. Your report has been submitted for review.');
    } catch (err) {
      alert('Failed to submit report.');
    } finally {
      setReportSubmitting(false);
    }
  };

  const toggleBookmark = async () => {
    if (!currentQ) return;
    try {
      const res = await ApiService.toggleBookmark(currentQ.id);
      setIsBookmarked(res.is_bookmarked);
      if (res.is_bookmarked) {
        setBookmarks(prev => prev.includes(currentQ.id) ? prev : [...prev, currentQ.id]);
      } else {
        setBookmarks(prev => prev.filter(id => id !== currentQ.id));
      }
    } catch (err) {
      console.error("Bookmark toggle failed", err);
    }
  };

  if (!currentQ) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <ConfirmationModal 
        isOpen={confirmLeave} 
        title="Protocol Termination?" 
        message="Your current progress is cached as a draft, but leaving now will pause the active assessment timer. Proceed?"
        confirmText="Leave Assessment"
        onConfirm={onCancel}
        onCancel={() => setConfirmLeave(false)}
        type="danger"
      />

      <ConfirmationModal 
        isOpen={confirmSubmit} 
        title="Incomplete Submission" 
        message={`You have ${questions.length - answeredCount} unanswered sectors. Do you wish to finalize your submission?`}
        confirmText="Finalize Submission"
        onConfirm={finishQuiz}
        onCancel={() => setConfirmSubmit(false)}
      />

      {/* Progress Bar */}
      <div className="w-full h-1.5 bg-slate-800">
        <motion.div 
          initial={{ width: 0 }} 
          animate={{ width: `${((currentIdx + 1) / questions.length) * 100}%` }} 
          className="h-full bg-gradient-to-r from-indigo-500 via-brand-primary to-purple-500" 
        />
      </div>

      <div className="max-w-7xl mx-auto w-full px-4 md:px-6 py-6 md:py-10 flex-1 flex gap-8">
        {/* LEFT SIDEBAR: Question Navigation */}
        <aside className="hidden lg:flex flex-col w-72 shrink-0 gap-6">
          <div className="bg-slate-900 border border-white/5 rounded-[2.5rem] p-8 flex flex-col shadow-2xl">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-brand-primary animate-pulse" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">Navigator</h3>
              </div>
              <span className="text-[10px] font-black text-brand-primary">{answeredCount}/{questions.length}</span>
            </div>

            <div className="grid grid-cols-4 gap-3 overflow-y-auto max-h-[50vh] pr-2 custom-scrollbar">
              {questions.map((_: any, i: number) => (
                <button
                  key={i}
                  onClick={() => { setDirection(i > currentIdx ? 1 : -1); setCurrentIdx(i); }}
                  className={`
                    h-12 rounded-xl text-[10px] font-black transition-all flex items-center justify-center relative border
                    ${i === currentIdx 
                      ? 'bg-brand-primary border-brand-primary text-slate-950 shadow-xl shadow-brand-primary/20 scale-110 z-10' 
                      : answers[i] 
                        ? 'bg-brand-primary/5 border-brand-primary/20 text-brand-primary' 
                        : 'bg-slate-950 border-white/5 text-slate-600 hover:text-white hover:bg-white/5'}
                  `}
                >
                  {i + 1}
                  {bookmarks.includes(questions[i]?.id) && (
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-amber-500 rounded-full border-2 border-slate-900" />
                  )}
                </button>
              ))}
            </div>

            <div className="mt-auto pt-8 border-t border-white/5 space-y-4">
              <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-slate-500">
                <span>Completion Status</span>
                <span>{Math.round((answeredCount / questions.length) * 100)}%</span>
              </div>
              <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                <motion.div animate={{ width: `${(answeredCount / questions.length) * 100}%` }} className="h-full bg-brand-primary" />
              </div>
            </div>
          </div>

          <div className="bg-slate-900/40 border border-white/5 p-6 rounded-[2rem] flex flex-col gap-4">
             <div className="flex items-center gap-3 text-slate-400">
                <Info size={16} />
                <span className="text-[10px] font-black uppercase tracking-[0.2em]">Operational Guide</span>
             </div>
             <p className="text-[11px] leading-relaxed text-slate-500 font-bold">
                Telemetry is synchronized in real-time. You can terminate the session and resume from any station.
             </p>
             <button onClick={() => setConfirmLeave(true)} className="mt-4 flex items-center justify-center gap-2 py-3 bg-white/5 hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all">
               <LogOut size={14} /> Terminate Protocol
             </button>
          </div>
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-1 flex flex-col">
          <div className="flex items-center justify-between gap-4 flex-wrap mb-6 md:mb-10">
            <div>
              <div className="flex items-center gap-2 text-brand-primary mb-1">
                <div className="w-1.5 h-1.5 rounded-full bg-brand-primary" />
                <span className="text-[10px] font-black uppercase tracking-[0.3em]">Data Sector {currentIdx + 1}</span>
              </div>
              <h2 className="text-2xl md:text-3xl font-black text-white">Assessment Query</h2>
            </div>

            <div className="flex items-center gap-2 md:gap-4">
              {bank.show_timer && (
                <div className={`flex items-center gap-4 px-6 py-3 rounded-2xl border transition-all ${
                  timeLeft <= 10 ? 'bg-rose-500/10 border-rose-500/50 text-rose-400 animate-pulse' : 'bg-slate-900 border-white/5 text-brand-primary'
                }`}>
                  <Timer size={20} />
                  <span className="text-xl font-black font-mono">
                    {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}
                  </span>
                </div>
              )}
              
              <div className="flex items-center gap-2 p-1 bg-slate-900 border border-white/5 rounded-2xl">
                 <button onClick={toggleBookmark} className={`p-3 rounded-xl transition-all ${isBookmarked ? 'bg-amber-500/10 text-amber-500' : 'text-slate-500 hover:text-white'}`}>
                   <Bookmark size={20} fill={isBookmarked ? "currentColor" : "none"} />
                 </button>
                 <button onClick={() => setShowDiscussions(true)} className="p-3 rounded-xl text-slate-500 hover:text-white transition-all">
                   <MessageSquare size={20} />
                 </button>
                 <button onClick={() => setShowReportModal(true)} className="p-3 rounded-xl text-slate-500 hover:text-rose-400 transition-all">
                   <AlertTriangle size={20} />
                 </button>
              </div>
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={currentIdx}
              initial={{ x: direction * 50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: direction * -50, opacity: 0 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="bg-slate-900 border border-white/5 rounded-3xl md:rounded-[3rem] p-5 md:p-12 shadow-2xl flex-1 flex flex-col"
            >
              <div className="text-lg md:text-xl font-bold text-slate-200 leading-relaxed mb-6 md:mb-12 break-words overflow-x-auto">
                <RichText text={currentQ.question} />
              </div>

              {currentQ.has_code ? (
                <div className="flex-1 min-h-[400px]">
                  <CodeEditor 
                    question={currentQ} 
                    onFinish={(res: any) => {
                      setAnswers({ ...answers, [currentIdx]: "COMPLETED" });
                      handleNext();
                    }} 
                  />
                </div>
              ) : ['mcq_multi', 'true_false', 'short_answer', 'essay'].includes(currentQ.question_type) ? (
                <QuestionCard
                  q={currentQ}
                  index={currentIdx}
                  value={answers[currentIdx] ?? (currentQ.question_type === 'mcq_multi' ? [] : '')}
                  onChange={(v) => setAnswers({ ...answers, [currentIdx]: v })}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {currentQ.options.map((opt: string, idx: number) => (
                    <button
                      key={idx}
                      onClick={() => setAnswers({ ...answers, [currentIdx]: opt })}
                      className={`p-4 md:p-6 rounded-3xl border-2 text-left transition-all flex items-center gap-4 md:gap-6 group ${
                        answers[currentIdx] === opt
                          ? 'bg-brand-primary/10 border-brand-primary text-white'
                          : 'bg-slate-950 border-white/5 text-slate-400 hover:border-white/10 hover:bg-white/5'
                      }`}
                    >
                      <div className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center font-black text-sm transition-all ${
                        answers[currentIdx] === opt ? 'bg-brand-primary text-slate-950' : 'bg-slate-900 text-slate-500 group-hover:text-white'
                      }`}>
                        {String.fromCharCode(65 + idx)}
                      </div>
                      <span className="font-bold min-w-0 break-words">{opt}</span>
                    </button>
                  ))}
                </div>
              )}

              {bank.allow_descriptive && (
                <div className="mt-12">
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Reasoning Artifact</label>
                    <span className="text-[10px] font-black text-slate-600">{notes[currentIdx]?.length || 0}/1000</span>
                  </div>
                  <textarea 
                    value={notes[currentIdx] || ''}
                    onChange={(e) => setNotes({...notes, [currentIdx]: e.target.value})}
                    placeholder="Describe your logical deduction for peer validation..."
                    className="w-full bg-slate-950 border border-white/5 rounded-2xl p-6 text-sm text-white outline-none focus:ring-1 focus:ring-brand-primary/50 transition-all resize-none h-32"
                  />
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          <div className="flex justify-between items-center mt-10">
            <button
              onClick={handlePrev}
              disabled={currentIdx === 0}
              className="flex items-center gap-3 px-8 py-4 bg-white/5 hover:bg-white/10 text-white rounded-2xl font-black uppercase tracking-widest text-[10px] disabled:opacity-0 transition-all"
            >
              <ChevronLeft size={16} /> Back Sector
            </button>
            <button
              onClick={handleNext}
              disabled={isSubmitting}
              className={`flex items-center gap-3 px-10 py-4 rounded-2xl font-black uppercase tracking-widest text-[10px] transition-all shadow-xl ${
                currentIdx === questions.length - 1 
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20' 
                  : 'bg-brand-primary hover:bg-brand-primary/90 text-slate-950 shadow-brand-primary/20'
              }`}
            >
              {currentIdx === questions.length - 1 ? 'Finalize Protocol' : 'Advance Sector'}
              <ChevronRight size={16} />
            </button>
          </div>
        </main>
      </div>

      {/* Modals */}
      <AnimatePresence>
        {showDiscussions && currentQ && (
          <QuestionDiscussions questionId={currentQ.id} onClose={() => setShowDiscussions(false)} />
        )}
        {showReportModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowReportModal(false)} className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} className="relative bg-slate-900 border border-white/10 p-10 rounded-[3rem] max-w-lg w-full shadow-2xl">
              <h3 className="text-2xl font-black text-white mb-6">Report Telemetry Anomaly</h3>
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3">
                  {['wrong_answer', 'typo', 'unclear', 'duplicate', 'other'].map(r => (
                    <button key={r} onClick={() => setReportReason(r)} className={`p-4 rounded-2xl border text-[10px] font-black uppercase tracking-widest transition-all ${reportReason === r ? 'bg-rose-500/20 border-rose-500 text-rose-400' : 'bg-slate-950 border-white/5 text-slate-500'}`}>
                      {r.replace('_', ' ')}
                    </button>
                  ))}
                </div>
                <textarea value={reportComment} onChange={e => setReportComment(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-6 text-white text-sm outline-none h-32 resize-none" placeholder="Describe the anomaly..." />
                <button onClick={submitReport} disabled={reportSubmitting} className="w-full py-5 bg-rose-600 text-white rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-rose-600/20">
                  {reportSubmitting ? 'Syncing...' : 'Submit Report'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
