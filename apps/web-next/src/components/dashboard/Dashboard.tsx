import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import ApiService from '../../services/ApiService';
import { LayoutDashboard, LogOut, BookOpen, Clock, Users, Trophy, ChevronRight, XCircle, Search, History, Trash2, Star, Plus, Timer, Shuffle, FileText, ClipboardList, Sparkles, Map } from 'lucide-react';
import BankCreationModal from './BankCreationModal';
import NotificationCenter from '../common/NotificationCenter';
import DailyChallengeModal from '../quiz/DailyChallengeModal';
import AINextTopicWidget from './AINextTopicWidget';
import { getIconSlug } from '../../data/bankIcons';

import { useToast } from '../ui/Toast';
import ExecutiveGrowthAtlas from './ExecutiveGrowthAtlas';
import AILearningPath from './AILearningPath';
import { RichText } from '../common/RichText';
import { SkeletonCard } from '../ui/Skeleton';

export default function Dashboard({ 
  user, 
  onLogout, 
  onStartQuiz, 
  onStartDailyChallenge, 
  onStartCoding, 
  onViewLeaderboard, 
  onViewProfile, 
  onViewForum,
  onViewAssignments,
  onViewHistory,
  onViewLibrary,
  onViewNotifications
}: any) {
  const { toast } = useToast();
  const [courses, setCourses] = useState<any[]>([]);
  const [banks, setBanks] = useState<any[]>([]);
  const [banksTotal, setBanksTotal] = useState(0);
  const [banksPage, setBanksPage] = useState(1);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  
  const [quizConfigModal, setQuizConfigModal] = useState<any>(null);
  const [quizMaxQuestions, setQuizMaxQuestions] = useState<number>(10);
  const [myStats, setMyStats] = useState<any>(null);
  const [showStats, setShowStats] = useState(false);
  const [activeTab, setActiveTab] = useState<'courses' | 'assignments' | 'coding' | 'bookmarks'>('courses');
  const [myAssignments, setMyAssignments] = useState<any[]>([]);
  const [codingQuestions, setCodingQuestions] = useState<any[]>([]);
  const [bookmarkedQuestions, setBookmarkedQuestions] = useState<any[]>([]);
  const [codingTotal, setCodingTotal] = useState(0);
  const [codingPage, setCodingPage] = useState(1);
  const [dailyChallenge, setDailyChallenge] = useState<any>(null);

  const [showBankModal, setShowBankModal] = useState(false);
  const [showLearningPath, setShowLearningPath] = useState(false);
  const [showDailyChallengeModal, setShowDailyChallengeModal] = useState(false);


  // Compute weakest bank from stats — PRD Section D "Needs Attention"
  const weakestBankId = useMemo(() => {
    if (!myStats?.banks_attempted || myStats.banks_attempted.length === 0) return null;
    // banks_attempted is sorted by accuracy ascending from the API
    const weakest = myStats.banks_attempted.reduce((min: any, b: any) => {
      const acc = b.total > 0 ? b.score / b.total : 1;
      const minAcc = min.total > 0 ? min.score / min.total : 1;
      return acc < minAcc ? b : min;
    }, myStats.banks_attempted[0]);
    return weakest?.bank_id ?? null;
  }, [myStats]);

  useEffect(() => {
    // group_id 0 is a valid group — guard on null/undefined, not falsiness.
    if (user.group_id == null) return;
    ApiService.getCourses(user.group_id)
      .then(res => {
        setCourses(Array.isArray(res) ? res : []);
        if (Array.isArray(res) && res.length > 0) {
          setSelectedCourseId(res[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch(err => {
        console.error("Failed to load courses", err);
        setLoading(false);
      });

    // Load My Stats on mount
    ApiService.getMyStats()
      .then(res => setMyStats(res))
      .catch(err => console.error("Failed to load stats", err));

    // (removed) 'nav-profile' window-event listener — nothing ever
    // dispatched it; navigation is router-based since Phase 4.

    // Load Daily Challenge on mount (not tab-dependent)
    ApiService.getDailyChallenge()
      .then(res => {
        if (res && res.question) setDailyChallenge(res);
        else setDailyChallenge(null);
      })
      .catch(() => setDailyChallenge(null));

  }, [user.group_id, onViewProfile]);

  useEffect(() => {
    if (activeTab === 'assignments') {
      setLoading(true);
      ApiService.getMyAssignments()
        .then(res => setMyAssignments(Array.isArray(res) ? res : []))
        .catch(err => console.error("Failed to load assignments", err))
        .finally(() => setLoading(false));
    } else if (activeTab === 'bookmarks') {
      setLoading(true);
      ApiService.getBookmarks()
        .then(res => setBookmarkedQuestions(Array.isArray(res) ? res : []))
        .catch(err => console.error("Failed to load bookmarks", err))
        .finally(() => setLoading(false));
    } else if (selectedCourseId !== null && activeTab === 'courses') {
      setLoading(true);
      // getBanks(courseId, page, size)
      ApiService.getBanks(selectedCourseId, banksPage)
        .then(res => {
          if (res && res.items) {
            setBanks(res.items);
            setBanksTotal(res.total);
          } else {
            setBanks(Array.isArray(res) ? res : []);
          }
        })
        .catch(err => console.error("Failed to load banks", err))
        .finally(() => setLoading(false));
    } else if (selectedCourseId !== null && activeTab === 'coding') {
      setLoading(true);
      ApiService.getCodingQuestions(selectedCourseId, codingPage)
        .then(res => {
          if (res && res.items) {
            setCodingQuestions(res.items);
            setCodingTotal(res.total);
          } else {
            setCodingQuestions(Array.isArray(res) ? res : []);
          }
        })
        .catch(err => console.error("Failed to load coding questions", err))
        .finally(() => setLoading(false));
    }
  }, [selectedCourseId, activeTab, banksPage, codingPage]);

  const handleStartAssignment = async (assignment: any) => {
    setLoading(true);
    try {
      if (assignment.is_daily_challenge) {
        setShowDailyChallengeModal(true);
        return;
      }
      if (assignment.bank_id) {

        // Find existing bank in memory or fetch
        let bank = banks.find(b => b.id === assignment.bank_id);
        if (!bank) {
          bank = await ApiService.getBankById(assignment.bank_id);
        }
        onStartQuiz(bank, bank.max_questions || 10);
      } else if (assignment.coding_question_id) {
        const q = await ApiService.getCodingQuestionById(assignment.coding_question_id);
        onStartCoding(q);
      }
    } catch (err: any) {
      toast('error', `Could not start assignment: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full flex gap-6">
      {/* Main Content */}
      <main className="flex-1 max-w-5xl px-8 py-10 w-full overflow-y-auto">
        
        {/* Course/Assignment Toggle */}
        <div className="flex flex-wrap gap-4 mb-8 bg-surface-container p-2 rounded-2xl w-fit">
           <button onClick={() => setActiveTab('courses')} className={`flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'courses' ? 'bg-brand-primary text-surface-dim shadow-lg shadow-brand-primary/20' : 'text-on-surface hover:bg-surface-container-high'}`}><BookOpen size={16} className="mr-2"/> Courses</button>
           <button onClick={() => setActiveTab('assignments')} className={`flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'assignments' ? 'bg-brand-primary text-surface-dim shadow-lg shadow-brand-primary/20' : 'text-on-surface hover:bg-surface-container-high'}`}><ClipboardList size={16} className="mr-2"/> Mandatory</button>
           <button onClick={() => setActiveTab('coding')} className={`flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'coding' ? 'bg-brand-primary text-surface-dim shadow-lg shadow-brand-primary/20' : 'text-on-surface hover:bg-surface-container-high'}`}><Sparkles size={16} className="mr-2"/> Coding</button>
           <button onClick={() => setActiveTab('bookmarks')} className={`flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === 'bookmarks' ? 'bg-brand-primary text-surface-dim shadow-lg shadow-brand-primary/20' : 'text-on-surface hover:bg-surface-container-high'}`}><Star size={16} className="mr-2"/> Bookmarks</button>
        </div>

        {/* Executive Growth Atlas — Section 12 Scientific Intelligence */}
        <div className="mb-12">
           <ExecutiveGrowthAtlas userId={user.id} />
        </div>

        {activeTab === 'courses' && (
          <div className="mb-10 w-full max-w-sm">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2 block">Selected Course</label>
            <select 
              value={selectedCourseId || ''} 
              onChange={(e) => setSelectedCourseId(Number(e.target.value))}
              className="w-full bg-surface-container border border-surface-bright rounded-xl px-4 py-3 text-on-surface font-semibold focus:outline-none focus:border-brand-primary"
            >
              <option value="" disabled>Select a course</option>
              {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        )}
        {activeTab === 'assignments' ? (
          <div>
            <div className="mb-10">
              <h3 className="text-3xl font-bold text-white mb-2">Mandatory Assignments</h3>
              <p className="text-slate-400">Complete these quizzes before the deadline.</p>
            </div>

            {dailyChallenge ? (
              <div className="mb-10 bg-gradient-to-r from-indigo-900/60 to-purple-900/60 border border-indigo-500/30 rounded-3xl p-8 relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500 opacity-10 blur-3xl rounded-full -mr-10 -mt-10 pointer-events-none group-hover:opacity-20 transition-opacity" />
                <div className="flex items-center gap-2 mb-4 text-indigo-400">
                   <Timer size={20} className="animate-pulse" />
                   <span className="font-bold uppercase tracking-widest text-sm">Challenge of the Day</span>
                </div>
                <h4 className="text-2xl font-bold text-white mb-4 line-clamp-2">{dailyChallenge.question?.question}</h4>
                <div className="flex items-center justify-between mt-6">
                  <span className={`px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider ${
                      dailyChallenge.question?.difficulty === 'Easy' ? 'bg-emerald-500/20 text-emerald-400' :
                      dailyChallenge.question?.difficulty === 'Medium' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-rose-500/20 text-rose-400'
                  }`}>
                    {dailyChallenge.question?.difficulty}
                  </span>
                  <button 
                    onClick={() => {
                        onStartDailyChallenge(dailyChallenge);
                    }}
                    className="bg-white text-indigo-950 px-6 py-2.5 rounded-xl font-bold hover:bg-indigo-50 transition-colors shadow-xl shadow-white/5"
                  >
                    Take Challenge
                  </button>
                </div>
              </div>
            ) : (
              <div className="mb-10 bg-slate-900/50 border border-slate-800 rounded-3xl p-8 text-center text-slate-400">
                <Timer size={32} className="mx-auto mb-4 opacity-50" />
                <p className="font-bold text-lg mb-1">No Daily Challenge Available</p>
                <p className="text-sm">Check back tomorrow for a new mandatory challenge.</p>
              </div>
            )}

            {loading ? (
                 <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div></div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {myAssignments.length === 0 ? (
                  <div className="col-span-full py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl">
                     <p className="text-slate-500">You have no pending mandatory assignments.</p>
                  </div>
                ) : (
                  myAssignments.map((a: any) => (
                    <motion.div key={a.assignment_id} whileHover={{ y: -4 }} className="bg-slate-900 border border-slate-800 rounded-3xl p-6 flex flex-col items-start shadow-xl relative overflow-hidden group">
                      <div className="flex w-full items-center justify-between mb-4">
                        <span className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${a.is_completed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                           {a.is_completed ? 'Completed' : 'Pending'}
                        </span>
                        <span className="text-xs font-mono text-slate-400"><Clock size={12} className="inline mr-1" /> {new Date(a.due_date).toLocaleDateString()}</span>
                      </div>
                      <h4 className="text-xl font-bold text-white mb-2 leading-tight">{a.bank_name}</h4>
                      
                      <div className="flex flex-wrap gap-2 mb-4">
                        {a.max_attempts && (
                          <span className="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded-lg border border-indigo-500/20 font-bold uppercase tracking-widest">
                            Max Attempts: {a.max_attempts}
                          </span>
                        )}
                        {a.passing_score_percent && (
                          <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded-lg border border-emerald-500/20 font-bold uppercase tracking-widest">
                            Passing: {a.passing_score_percent}%
                          </span>
                        )}
                        {a.lock_after_due && (
                          <span className="text-[10px] bg-rose-500/10 text-rose-400 px-2 py-1 rounded-lg border border-rose-500/20 font-bold uppercase tracking-widest">
                            Due Lock
                          </span>
                        )}
                      </div>

                      {a.is_completed ? (
                        <p className="text-emerald-400 font-bold mb-4 text-sm mt-auto">Score: {a.score}</p>
                      ) : (
                        <button 
                          onClick={() => handleStartAssignment(a)}
                          className="w-full mt-auto py-3 bg-brand-primary text-surface-dim rounded-xl font-black text-sm transition-all hover:scale-[1.02]"
                        >
                          Start Assignment
                        </button>
                      )}
                    </motion.div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : activeTab === 'bookmarks' ? (
          <div>
            <div className="mb-10">
              <h3 className="text-3xl font-bold text-white mb-2">Bookmarked Questions</h3>
              <p className="text-slate-400">Review your saved questions for later study.</p>
            </div>
            
            {loading ? (
              <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary"></div></div>
            ) : (
              <div className="space-y-6">
                {bookmarkedQuestions.length === 0 ? (
                  <div className="py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl">
                     <p className="text-slate-500">You haven't bookmarked any questions yet.</p>
                  </div>
                ) : (
                  bookmarkedQuestions.map((q: any) => (
                    <motion.div key={q.id} whileHover={{ x: 4 }} className="bg-surface-container border border-surface-bright rounded-3xl p-6 shadow-xl group">
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-3">
                           <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
                             <Star size={18} fill="currentColor" />
                           </div>
                           <div>
                             <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Saved Question</p>
                             <p className="text-xs font-bold text-slate-400">Question ID: #{q.id}</p>
                           </div>
                        </div>
                        <button 
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              await ApiService.toggleBookmark(q.id);
                              setBookmarkedQuestions(prev => prev.filter(item => item.id !== q.id));
                              toast('success', 'Removed from bookmarks');
                            } catch {
                              toast('error', 'Failed to remove bookmark');
                            }
                          }}
                          className="p-2 hover:bg-rose-500/10 text-slate-600 hover:text-rose-400 rounded-xl transition-all"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                      
                      <div className="mb-6">
                        <RichText text={q.question} />
                      </div>
                      
                      <div className="flex flex-wrap gap-2 mb-6">
                         {q.options.map((opt: string, idx: number) => (
                           <div key={idx} className={`px-4 py-2 rounded-xl text-xs font-bold border ${q.answer === opt ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-slate-950 border-white/5 text-slate-500'}`}>
                             {opt}
                           </div>
                         ))}
                      </div>

                      {q.explanation && (
                        <div className="p-4 bg-slate-950 rounded-2xl border border-white/5 text-xs text-slate-400 leading-relaxed">
                          <span className="font-black text-brand-primary uppercase tracking-widest mr-2">Explanation:</span>
                          {q.explanation}
                        </div>
                      )}
                    </motion.div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : activeTab === 'coding' ? (
          <div>
            <div className="mb-10">
              <h3 className="text-3xl font-bold text-white mb-2">Coding Practice</h3>
              <p className="text-slate-400">Master concepts with AI-evaluated coding challenges.</p>
            </div>
            
            {loading ? (
              <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary"></div></div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {codingQuestions.map((q: any) => (
                  <motion.div key={q.id} whileHover={{ y: -4 }} className="bg-surface-container border border-surface-bright rounded-3xl p-6 flex flex-col h-full shadow-xl">
                    <div className="flex justify-between mb-4">
                       <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${
                         q.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                         q.difficulty === 'Medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                         'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                       }`}>
                         {q.difficulty}
                       </span>
                       <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{q.language}</span>
                    </div>
                    <h4 className="text-lg font-bold text-white mb-4">{q.title}</h4>
                    <p className="text-sm text-on-surface-variant mb-6 line-clamp-2 h-10">{q.description}</p>
                    <button 
                      onClick={() => onStartCoding(q)}
                      className="mt-auto w-full py-3 bg-brand-primary text-surface-dim rounded-xl font-black text-sm transition-all hover:scale-[1.02] active:scale-[0.98]"
                    >
                      Attempt Hub
                    </button>
                  </motion.div>
                ))}
              </div>
              
              {codingTotal > 50 && (
                <div className="flex justify-center items-center gap-4 mt-10">
                  <button 
                    disabled={codingPage === 1}
                    onClick={() => setCodingPage(p => p - 1)}
                    className="px-4 py-2 bg-surface-container border border-surface-bright rounded-xl text-on-surface disabled:opacity-30"
                  >
                    Previous
                  </button>
                  <span className="text-sm font-bold text-on-surface-variant">Page {codingPage}</span>
                  <button 
                    disabled={codingPage * 50 >= codingTotal}
                    onClick={() => setCodingPage(p => p + 1)}
                    className="px-4 py-2 bg-surface-container border border-surface-bright rounded-xl text-on-surface disabled:opacity-30"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
        ) : (
          <>
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-10 gap-4">
          <div>
            <h3 className="text-3xl font-bold text-white mb-2">Question Banks</h3>
            <p className="text-slate-400">Select a bank to challenge your skills.</p>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
            <button 
              onClick={() => setShowLearningPath(true)}
              className="flex items-center justify-center gap-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 px-5 py-3 rounded-2xl font-bold border border-purple-500/20 shadow-lg shadow-purple-500/10 transition-all active:scale-[0.98] whitespace-nowrap"
            >
              <Sparkles size={18} /> AI Path
            </button>
            <button 
              onClick={() => setShowBankModal(true)}
              className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-3 rounded-2xl font-bold shadow-lg shadow-indigo-500/30 transition-all active:scale-[0.98] whitespace-nowrap"
            >
              <Plus size={18} /> Create Bank
            </button>
            <div className="relative w-full sm:w-64 border-slate-700">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search banks..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-2xl pl-12 pr-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all shadow-inner"
              />
            </div>
          </div>
          
          {banksTotal > 50 && (
            <div className="flex justify-center items-center gap-4 mt-10">
              <button 
                disabled={banksPage === 1}
                onClick={() => setBanksPage(p => p - 1)}
                className="px-4 py-2 bg-surface-container border border-surface-bright rounded-xl text-on-surface disabled:opacity-30"
              >
                Previous
              </button>
              <span className="text-sm font-bold text-on-surface-variant">Page {banksPage}</span>
              <button 
                disabled={banksPage * 50 >= banksTotal}
                onClick={() => setBanksPage(p => p + 1)}
                className="px-4 py-2 bg-surface-container border border-surface-bright rounded-xl text-on-surface disabled:opacity-30"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {loading ? (
             <div className="flex items-center justify-center py-20"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {banks.filter(b => b.name.toLowerCase().includes(searchQuery.toLowerCase())).map(bank => {
              const isWeakest = bank.id === weakestBankId;
              const iconName = getIconSlug(bank);

              return (
              <motion.div
                key={bank.id}
                whileHover={{ y: -4, scale: 1.01 }}
                className={`bg-surface-container border rounded-3xl p-6 flex flex-col h-full shadow-2xl relative overflow-hidden group transition-all
                  ${isWeakest
                    ? 'border-indigo-500/40 ring-2 ring-indigo-500/20 shadow-[0_0_30px_rgba(99,102,241,0.15)]'
                    : 'border-surface-bright hover:border-brand-primary/50'
                  }`}
              >
                {/* "Needs Attention" badge — PRD Section D */}
                {isWeakest && (
                  <div className="absolute top-3 left-3 z-10">
                    <span className="px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-400
                                     text-[9px] font-black uppercase tracking-widest border border-indigo-500/30
                                     shadow-[0_0_12px_rgba(99,102,241,0.3)]">
                      Needs Attention
                    </span>
                  </div>
                )}

                {/* Decorative bloom behind the difficulty tag */}
                <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br opacity-5 blur-3xl rounded-full -mr-10 -mt-10 pointer-events-none transition-opacity group-hover:opacity-20 ${
                    bank.difficulty === 'Easy' ? 'from-emerald-500 to-emerald-300' :
                    bank.difficulty === 'Medium' ? 'from-amber-500 to-amber-300' :
                    bank.difficulty === 'Hard' ? 'from-rose-500 to-rose-300' : 'from-indigo-500 to-purple-500'
                }`} />

                {/* ─── SECTION D: Icon + Difficulty Badge ─────────────── */}
                <div className="flex justify-between items-start mb-6 align-top">
                  {/* Icon — auto-detected from bank chapter/name */}
                  <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center
                                  group-hover:scale-110 transition-transform border border-slate-700">
                    <span className="material-symbols-outlined text-indigo-400 text-2xl">
                      {iconName}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Difficulty pill — PRD Section D */}
                    <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${
                        bank.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                        bank.difficulty === 'Medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                        bank.difficulty === 'Hard' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                        'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                      }`}>
                      {bank.difficulty}
                    </span>
                    {bank.created_by === user.full_name && (
                       <button onClick={(e) => {
                          e.stopPropagation();
                          if(confirm(`Delete ${bank.name}?`)) {
                             ApiService.deleteBank(bank.id).then(() => setBanks(banks.filter(b => b.id !== bank.id)));
                          }
                       }} className="text-slate-600 hover:text-rose-500 transition-colors p-1" title="Delete Bank"><Trash2 size={16}/></button>
                    )}
                  </div>
                </div>

                <h4 className="text-xl font-bold text-white mb-2 leading-tight group-hover:text-brand-primary transition-colors">{bank.name}</h4>
                <p className="text-on-surface-variant text-sm mb-6 line-clamp-2 md:h-10">{bank.description || 'No description provided.'}</p>

                {/* ─── SECTION D: 2-Column Stat Grid ─────────────────── */}
                <div className="grid grid-cols-2 gap-3 mt-auto mb-6 pt-4 border-t border-slate-800">
                  {[
                    { icon: 'quiz',     value: `${bank.question_count} questions` },
                    { icon: 'schedule', value: `${bank.time_per_question || 30}s / q` },
                    { icon: 'history',  value: `${bank.attempt_count || 0} attempts` },
                    { icon: 'book',     value: bank.chapter || bank.difficulty },
                  ].map(stat => (
                    <div key={stat.icon} className="flex items-center gap-2 text-slate-400">
                      <span className="material-symbols-outlined text-indigo-400"
                            style={{ fontSize: '14px' }}>{stat.icon}</span>
                      <span className="text-xs font-medium">{stat.value}</span>
                    </div>
                  ))}
                </div>

                {/* Settings badges — show what the creator configured */}
                <div className="flex flex-wrap gap-2 mb-6">
                  {bank.show_timer !== false && (
                    <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <Timer size={10} /> Timer
                    </span>
                  )}
                  {bank.shuffle !== false && (
                    <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      <Shuffle size={10} /> Shuffled
                    </span>
                  )}
                  {bank.allow_descriptive !== false && (
                    <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <FileText size={10} /> Notes
                    </span>
                  )}
                </div>

                <div className="mt-auto flex gap-3 z-10">
                  <button
                    onClick={() => setQuizConfigModal(bank)}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl transition-all font-bold text-sm shadow-lg shadow-indigo-600/20 active:scale-[0.98]"
                  >
                    Start Quiz
                  </button>
                  <button
                    onClick={() => onViewLeaderboard(bank)}
                    className="p-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-colors border border-slate-700 hover:border-slate-600"
                    title="Leaderboard"
                  >
                    <Trophy size={20} />
                  </button>
                </div>
              </motion.div>
            );
            })}
            {loading && banks.length === 0 && (
              <>{Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} className="h-40" lines={2} />)}</>
            )}
            {banks.length === 0 && !loading && (
               <div className="col-span-full py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl">
                  <p className="text-slate-500">No question banks found for this course.</p>
               </div>
            )}
          </div>
        )}
        </>
        )}

        {/* Start Quiz Modal */}
        <AnimatePresence>
          {quizConfigModal && (
            <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-slate-900 border border-slate-800 p-8 rounded-3xl w-full max-w-sm shadow-2xl relative overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-purple-500" />
                <div className="flex justify-between items-start mb-6 pt-2">
                  <h3 className="text-xl font-bold text-white pr-4 leading-tight">Start: {quizConfigModal.name}</h3>
                  <button onClick={() => setQuizConfigModal(null)} className="text-slate-500 hover:text-white shrink-0">
                    <XCircle size={24} />
                  </button>
                </div>

                <div className="mb-8">
                  <label className="block text-sm font-medium text-slate-400 mb-2">Questions to attempt</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={quizMaxQuestions}
                      onChange={e => setQuizMaxQuestions(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-4 pl-12 text-white text-lg font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      min={1}
                      max={quizConfigModal.question_count}
                    />
                    <BookOpen size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                  </div>
                  <div className="flex justify-between mt-2 px-1">
                     <p className="text-xs text-slate-500">Available: {quizConfigModal.question_count}</p>
                     <button onClick={() => setQuizMaxQuestions(quizConfigModal.question_count)} className="text-xs text-indigo-400 font-bold hover:underline">Select All</button>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setQuizConfigModal(null)}
                    className="flex-1 bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-bold transition-all border border-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => onStartQuiz(quizConfigModal, quizMaxQuestions)}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30"
                  >
                    Begin
                  </button>
                </div>
              </motion.div>
            </div>
          )}
          
          {showBankModal && (
            <BankCreationModal 
              user={user}
              courses={courses}
              onClose={() => setShowBankModal(false)}
              onCreated={() => {
                setShowBankModal(false);
                // Refresh banks
                if (selectedCourseId) {
                  ApiService.getBanks(selectedCourseId, 1).then(res => {
                    if (res && res.items) setBanks(res.items);
                    else setBanks(Array.isArray(res) ? res : []);
                  });
                }
              }}
            />
          )}
          
          {showDailyChallengeModal && dailyChallenge && (
            <DailyChallengeModal
              challenge={dailyChallenge}
              onClose={() => setShowDailyChallengeModal(false)}
              onSuccess={() => {
                // Refresh assignments or stats
                ApiService.getMyStats().then(res => setMyStats(res));
                setShowDailyChallengeModal(false);
              }}
            />
          )}

          {showLearningPath && (
            <AILearningPath onClose={() => setShowLearningPath(false)} />
          )}
        </AnimatePresence>
      </main>

      {/* Right AI Sidebar */}
      <aside className="hidden xl:flex w-72 shrink-0 py-10 pr-8 flex-col gap-4">
        <div 
          onClick={onViewForum}
          className="p-6 bg-gradient-to-br from-indigo-600/20 to-violet-600/20 border border-indigo-500/30 rounded-3xl cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-all group"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 group-hover:rotate-12 transition-transform">
              <Users size={20} />
            </div>
            <div>
              <p className="text-sm font-black text-white">Community</p>
              <p className="text-[10px] text-indigo-400 font-bold uppercase tracking-widest">Discussion Forum</p>
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Collaborate with peers, share tactical insights, and upvote the best solutions.
          </p>
        </div>

        {/* Quick Navigation Section */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-5 mb-4">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-4">Navigation</p>
          <div className="space-y-1">
            {[
              { label: 'Assignments', icon: ClipboardList, color: 'text-rose-400', onClick: onViewAssignments },
              { label: 'Attempt History', icon: History, color: 'text-amber-400', onClick: onViewHistory },
              { label: 'Question Library', icon: BookOpen, color: 'text-indigo-400', onClick: onViewLibrary },
              { label: 'Notifications', icon: Timer, color: 'text-emerald-400', onClick: onViewNotifications },
            ].map(nav => (
              <button 
                key={nav.label}
                onClick={nav.onClick}
                className="w-full flex items-center justify-between p-3 rounded-2xl hover:bg-white/5 transition-all group text-left"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-xl bg-slate-950 flex items-center justify-center ${nav.color}`}>
                    <nav.icon size={16} />
                  </div>
                  <span className="text-xs font-bold text-slate-300 group-hover:text-white transition-colors">{nav.label}</span>
                </div>
                <ChevronRight size={14} className="text-slate-600 group-hover:text-white group-hover:translate-x-1 transition-all" />
              </button>
            ))}
          </div>
        </div>

        <AINextTopicWidget groupId={user?.group_id} />

        {/* Quick Stats Card */}
        {myStats && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/60 border border-slate-800 rounded-3xl p-5"
          >
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-4">My Progress</p>
            <div className="space-y-3">
              {[
                { label: 'Total Attempts', value: myStats.total_attempts || 0, color: 'text-indigo-400' },
                { label: 'Avg Accuracy', value: `${myStats.overall_accuracy || 0}%`, color: myStats.overall_accuracy >= 70 ? 'text-emerald-400' : myStats.overall_accuracy >= 40 ? 'text-amber-400' : 'text-rose-400' },
                { label: 'Streak 🔥', value: `${myStats.streak_count || 0} days`, color: 'text-orange-400' },
              ].map(stat => (
                <div key={stat.label} className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">{stat.label}</span>
                  <span className={`text-sm font-black ${stat.color}`}>{stat.value}</span>
                </div>
              ))}
            </div>
            <button 
              onClick={onViewHistory}
              className="w-full mt-6 py-3 bg-white/5 hover:bg-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-slate-300 transition-all border border-white/5"
            >
              View Detailed History
            </button>
          </motion.div>
        )}
      </aside>
    </div>
  );
}
