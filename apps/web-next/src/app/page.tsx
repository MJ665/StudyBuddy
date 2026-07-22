'use client';

import React, { useState, useEffect, useTransition } from 'react';
import { ToastProvider, useToast } from '@/components/ui/Toast';
import { motion, AnimatePresence } from 'motion/react';
import { Trophy, Target, Clock, ChevronRight, RotateCcw, BrainCircuit, CheckCircle2 } from 'lucide-react';

import ApiService from '@/services/ApiService';
import LoginView from '@/components/auth/LoginView';
import ForgotPasswordPage from '@/components/auth/ForgotPasswordPage';
import ResetPasswordPage from '@/components/auth/ResetPasswordPage';
import Dashboard from '@/components/dashboard/Dashboard';
import QuizFlow from '@/components/quiz/QuizFlow';
import Leaderboard from '@/components/leaderboard/Leaderboard';
import ResourceCenter from '@/components/resources/ResourceCenter';
import LDAdminDashboard from '@/components/dashboard/LDAdminDashboard';
import MentorDashboard from '@/components/dashboard/MentorDashboard';
import AdministrationEngine from '@/components/dashboard/AdministrationEngine';
import CodeEditor from '@/components/quiz/CodeEditor';
import UserProfile from '@/components/profile/UserProfile';
import DiscussionForum from '@/components/dashboard/DiscussionForum';
import QuestionLibrary from '@/components/dashboard/QuestionLibrary';
import AssignmentsView from '@/components/dashboard/AssignmentsView';
import AttemptHistory from '@/components/profile/AttemptHistory';
import NotificationsView from '@/components/dashboard/NotificationsView';
import ExecutiveReport from '@/components/dashboard/ExecutiveReport';
import AILearningPath from '@/components/dashboard/AILearningPath';
import AIQuizGenerator from '@/components/dashboard/AIQuizGenerator';
import NotificationCenter from '@/components/common/NotificationCenter';
import { AppLayout } from '@/components/ui/AppLayout';
import UserIntelPanel from '@/components/dashboard/UserIntelPanel';
import PublicProfile from '@/components/profile/PublicProfile';

import KTNavShell from '@/components/kt/KTNavShell';
import KTBreadcrumb from '@/components/kt/KTBreadcrumb';
import KTViewport from '@/components/kt/KTViewport';

// --- Quiz Result Screen ---
function QuizResultScreen({ result, bank, onViewLeaderboard, onRetake }: any) {
  const accuracy = result.total > 0 ? Math.round((result.score / result.total) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="min-h-screen bg-slate-950 text-slate-200 flex items-center justify-center p-6"
    >
      <div className="w-full max-w-2xl">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-10 shadow-2xl text-center mb-8 relative overflow-hidden">
          <div className={`absolute inset-0 opacity-5 pointer-events-none ${
            accuracy >= 70 ? 'bg-gradient-to-br from-emerald-500 to-teal-500' : 
            accuracy >= 40 ? 'bg-gradient-to-br from-amber-500 to-orange-500' : 
            'bg-gradient-to-br from-rose-500 to-pink-500'
          }`} />
          
          <div className={`w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl font-black border-4 ${
            accuracy >= 70 ? 'border-emerald-500 bg-emerald-900/20 text-emerald-400' :
            accuracy >= 40 ? 'border-amber-500 bg-amber-900/20 text-amber-400' :
            'border-rose-500 bg-rose-900/20 text-rose-400'
          }`}>
            {accuracy}%
          </div>
          
          <h2 className="text-3xl font-bold text-white mb-2">Quiz Complete!</h2>
          <p className="text-slate-400 mb-8">{bank?.name || 'Assessment'}</p>
          
          <div className="grid grid-cols-4 gap-3 mb-8">
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Trophy size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">{result.score}/{result.total}</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Raw Score</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <BrainCircuit size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">{result.weighted_score?.toFixed(1) || '0.0'}/{result.total_weight?.toFixed(1) || '0.0'}</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Weighted</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Target size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">{accuracy}%</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Accuracy</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Clock size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">{Math.floor(result.timeTaken / 60)}m {result.timeTaken % 60}s</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Time</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={onRetake}
              className="flex-1 flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-bold transition-all border border-slate-700"
            >
              <RotateCcw size={18} /> Retake
            </button>
            <button
              onClick={onViewLeaderboard}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30"
            >
              View Leaderboard <ChevronRight size={18} />
            </button>
          </div>
        </div>

        {result.breakdown && result.breakdown.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl">
            <h3 className="font-bold text-white mb-4 text-lg">Answer Breakdown</h3>
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
              {result.breakdown.map((item: any, i: number) => (
                <div key={i} className={`p-4 rounded-xl border text-sm ${
                  item.is_correct 
                    ? 'bg-emerald-900/10 border-emerald-500/20' 
                    : 'bg-rose-900/10 border-rose-500/20'
                }`}>
                  <p className="text-slate-300 font-medium mb-2">{i + 1}. {item.question_text}</p>
                  <div className="flex gap-4 flex-wrap mb-2">
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      item.is_correct ? 'bg-emerald-900/30 text-emerald-400' : 'bg-rose-900/30 text-rose-400'
                    }`}>
                      Your: {item.user_answer || 'Skipped'}
                    </span>
                    {!item.is_correct && (
                      <span className="text-xs font-bold px-2 py-1 rounded bg-emerald-900/30 text-emerald-400">
                        Correct: {item.correct_answer}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// --- Main App Inner ---
function AppInner() {
  const { toast } = useToast();
  const [user, setUser] = useState<any>(null);
  const [currentView, setCurrentView] = useState<string>('LOGIN');
  const [recoveryData, setRecoveryData] = useState<{ email: string; groupId: number } | null>(null);
  const [activeBank, setActiveBank] = useState<any>(null);
  const [activeQuestions, setActiveQuestions] = useState<any[]>([]);
  const [quizResult, setQuizResult] = useState<any>(null);
  const [profileSlug, setProfileSlug] = useState<string | null>(null);
  const [reportBatchId, setReportBatchId] = useState<number | null>(null);
  const [selectedUserSlug, setSelectedUserSlug] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [showAIPath, setShowAIPath] = useState(false);
  const [showAIQuiz, setShowAIQuiz] = useState(false);
  const [isPending, startTransition] = useTransition();

  const handleLoginSuccess = (userData: any) => {
    console.log("🔐 Login Success. Current View:", currentView, "Path:", window.location.pathname);
    setUser(userData);
    
    // 1. If we are currently on a public profile URL, stay there but show the profile view
    const path = window.location.pathname;
    if (path.startsWith('/profile/') || path.startsWith('/p/')) {
      console.log("📍 Public Profile Detected. Staying on view.");
      setCurrentView('PUBLIC_PROFILE');
      return;
    }

    // 2. Only auto-redirect to role-based dashboard if we are on the login screen
    if (currentView === 'LOGIN') {
      console.log("🏠 Redirecting to Role-Based Dashboard.");
      if (userData.role === 'LDAdmin') setCurrentView('LD_ADMIN');
      else if (userData.role === 'Mentor') setCurrentView('MENTOR');
      else if (userData.role === 'GroupAdmin') setCurrentView('ADMIN');
      else setCurrentView('DASHBOARD');
    }
  };

  const handleLogout = () => {
    ApiService.logout();
    setUser(null);
    setCurrentView('LOGIN');
    window.history.pushState({}, '', '/');
  };

  useEffect(() => {
    const hydrateSession = async () => {
      try {
        const me = await ApiService.getMe();
        if (me && me.success) {
          handleLoginSuccess(me);
        }
      } catch (err) { /* Not logged in */ }
    };
    hydrateSession();

    const handleLocationChange = () => {
      const path = window.location.pathname;
      if (path.startsWith('/p/') || path.startsWith('/profile/')) {
        const parts = path.split('/').filter(Boolean);
        const slug = parts[parts.length - 1];
        if (slug && slug !== 'profile' && slug !== 'p') {
          setProfileSlug(slug);
          setCurrentView('PUBLIC_PROFILE');
        }
      } else if (path === '/reset-password') {
        setCurrentView('RESET_PASSWORD');
      } else if (path.startsWith('/kt')) {
        setCurrentView('KNOWLEDGE_HUB');
        const parts = path.split('/').filter(Boolean);
        // Path matches: kt, company, {id}, project, {id}
        if (parts.length >= 3 && parts[1] === 'company') {
          const companyId = parts[2];
          // Dispatch a custom event for KTNavShell/NavStore to pick up the company,
          // since the store is outside of page.tsx state context or we can just let
          // the store sync it itself if we want, but letting page.tsx handle it is fine.
          // The easiest way is to let KTNavShell or the store parse it on init.
        }
      }
    };
    handleLocationChange();
    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);

  const handleStartQuiz = (bank: any, maxQuestions: number) => {
    startTransition(async () => {
      try {
        const questions = await ApiService.getQuizQuestions(bank.id, maxQuestions);
        setActiveBank(bank);
        setActiveQuestions(questions);
        setCurrentView('QUIZ');
      } catch (err: any) {
        toast('error', `Failed to start quiz: ${err.message}`);
      }
    });
  };

  const handleStartDailyChallenge = (challenge: any) => {
    startTransition(() => {
      setActiveBank({ name: 'Daily Challenge', id: challenge.question.bank_id });
      setActiveQuestions([challenge.question]);
      setCurrentView('QUIZ');
    });
  };

  const handleStartCoding = (question: any) => {
    setActiveBank(question);
    setCurrentView('CODING_FLOW');
  };

  const handleQuizFinish = (result: any) => {
    const question_ids = activeQuestions.map(q => q.id);
    const user_answers = activeQuestions.map((_, i) => result.answers[i] || "");
    const user_notes = activeQuestions.map((_, i) => result.notes[i] || "");

    startTransition(() => {
      if (result.submitResult) {
        setQuizResult({ ...result.submitResult, timeTaken: result.timeTaken });
        setCurrentView('QUIZ_RESULT');
        toast('success', `Quiz submitted! Score: ${result.submitResult.score}/${result.submitResult.total}`);
      } else {
        toast('error', `Failed to submit quiz: No result returned.`);
      }
    });
  };

  const renderView = () => {
    // Public/Auth routes first
    if (currentView === 'FORGOT_PASSWORD') {
      return <ForgotPasswordPage 
        onBack={() => setCurrentView('LOGIN')} 
        onSuccess={(email, groupId) => {
          setRecoveryData({ email, groupId });
          setCurrentView('RESET_PASSWORD');
        }}
      />;
    }

    if (currentView === 'RESET_PASSWORD') {
      return <ResetPasswordPage 
        email={recoveryData?.email}
        groupId={recoveryData?.groupId}
        onBack={() => setCurrentView('LOGIN')}
        onSuccess={() => {
          setRecoveryData(null);
          setCurrentView('LOGIN');
          toast('success', 'Credentials updated. Please authenticate.');
        }}
      />;
    }

    if (currentView === 'PUBLIC_PROFILE' && profileSlug) {
      return <PublicProfile 
        slug={profileSlug} 
        isLoggedIn={!!user}
        onLoginClick={() => setCurrentView('LOGIN')}
        onBack={() => {
          if (!user) {
            setCurrentView('LOGIN');
            window.history.pushState({}, '', '/');
          }
          else if (user.role === 'LDAdmin') setCurrentView('LD_ADMIN');
          else if (user.role === 'Mentor') setCurrentView('MENTOR');
          else setCurrentView('DASHBOARD');
          
          if (user) window.history.pushState({}, '', '/');
        }} 
      />;
    }

    if (!user) {
      return <LoginView 
        onLoginSuccess={handleLoginSuccess} 
        onForgotPassword={() => setCurrentView('FORGOT_PASSWORD')}
      />;
    }

    switch (currentView) {
      case 'DASHBOARD': 
        return <Dashboard
          user={user}
          onLogout={handleLogout}
          onStartQuiz={handleStartQuiz}
          onStartDailyChallenge={handleStartDailyChallenge}
          onStartCoding={handleStartCoding}
          onViewLeaderboard={(bank: any) => { setActiveBank(bank); setCurrentView('LEADERBOARD'); }}
          onViewProfile={() => setCurrentView('PROFILE')}
          onViewForum={() => setCurrentView('DISCUSSIONS')}
          onViewAssignments={() => setCurrentView('ASSIGNMENTS')}
          onViewHistory={() => setCurrentView('ATTEMPT_HISTORY')}
          onViewLibrary={() => setCurrentView('LIBRARY')}
          onViewNotifications={() => setCurrentView('NOTIFICATIONS')}
        />;
      
      case 'LD_ADMIN':
        return <LDAdminDashboard 
          user={user} 
          onLogout={handleLogout} 
          onViewReport={(id) => { setReportBatchId(id); setCurrentView('BATCH_REPORT'); }} 
          onViewPremium={(slugOrId) => { 
            console.log("🚀 Viewing Premium Profile for:", slugOrId);
            if (typeof slugOrId === 'number') {
              setSelectedUserId(slugOrId);
              // If it's a number, we don't have a slug, so we use the ID as slug if needed
              setProfileSlug(slugOrId.toString());
            } else {
              setSelectedUserSlug(slugOrId);
              setProfileSlug(slugOrId);
            }
            setCurrentView('PUBLIC_PROFILE'); 
            window.history.pushState({}, '', `/profile/${slugOrId}`);
          }}
        />;
      
      case 'MENTOR':
        return <MentorDashboard user={user} onBack={() => setCurrentView('DASHBOARD')} />;
      
      case 'ADMIN':
        return <AdministrationEngine 
          user={user} 
          onBack={() => setCurrentView('DASHBOARD')} 
          onViewReport={(batchId) => { setReportBatchId(batchId); setCurrentView('BATCH_REPORT'); }} 
          onViewForum={() => setCurrentView('DISCUSSIONS')} 
          onViewPremium={(slugOrId) => { 
            if (typeof slugOrId === 'number') {
              setSelectedUserId(slugOrId);
              setProfileSlug(slugOrId.toString());
            } else {
              setSelectedUserSlug(slugOrId);
              setProfileSlug(slugOrId);
            }
            setCurrentView('PUBLIC_PROFILE'); 
            window.history.pushState({}, '', `/profile/${slugOrId}`);
          }} 
        />;

      case 'BATCH_REPORT':
        return reportBatchId ? <ExecutiveReport batchId={reportBatchId} onBack={() => setCurrentView('LD_ADMIN')} /> : null;

      case 'QUIZ':
        return <QuizFlow
          bank={activeBank} 
          questions={activeQuestions} 
          user={user}
          onFinish={handleQuizFinish}
          onCancel={() => setCurrentView('DASHBOARD')}
        />;

      case 'QUIZ_RESULT':
        return <QuizResultScreen 
          result={quizResult} 
          bank={activeBank}
          onViewLeaderboard={() => setCurrentView('LEADERBOARD')}
          onRetake={() => handleStartQuiz(activeBank, activeQuestions.length)}
        />;

      case 'CODING_FLOW':
        return <div className="h-full w-full p-8 flex flex-col">
          <CodeEditor 
            question={activeBank} 
            onFinish={(res: any) => {
              setQuizResult(res);
              setCurrentView('CODING_RESULT');
            }} 
          />
        </div>;

      case 'CODING_RESULT':
        return <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
          <div className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-10 max-w-lg w-full text-center">
            <div className="w-20 h-20 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-6 text-emerald-400">
              <CheckCircle2 size={32} />
            </div>
            <h3 className="text-3xl font-black text-white mb-2">Code Accepted!</h3>
            <p className="text-slate-400 mb-8">Your solution passed the AI rubric with a score of <span className="text-white font-bold">{quizResult?.score}%</span></p>
            <button onClick={() => setCurrentView('DASHBOARD')} className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-black uppercase tracking-widest transition-all">Return to Dashboard</button>
          </div>
        </div>;

      case 'LEADERBOARD':
        return <Leaderboard bank={activeBank} user={user} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'PROFILE':
        return <UserProfile isOwnProfile={true} slug={user?.email?.split('@')[0]} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'DISCUSSIONS':
        return <DiscussionForum user={user} onViewProfile={(slug) => { setSelectedUserSlug(slug); setCurrentView('USER_INTEL'); }} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'LIBRARY':
        return <QuestionLibrary user={user} onStartQuiz={handleStartQuiz} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'ASSIGNMENTS':
        return <AssignmentsView user={user} onStartQuiz={handleStartQuiz} onStartCoding={handleStartCoding} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'ATTEMPT_HISTORY':
        return <AttemptHistory user={user} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'NOTIFICATIONS':
        return <NotificationsView user={user} onBack={() => setCurrentView('DASHBOARD')} onNavigate={(type) => type === 'new_assignment' && setCurrentView('ASSIGNMENTS')} />;

      case 'RESOURCES':
        return <ResourceCenter user={user} group={{id: user?.group_id, name: user?.group_name || 'Your Group'}} onBack={() => setCurrentView('DASHBOARD')} />;

      case 'USER_INTEL':
        return <UserIntelPanel userId={selectedUserId || user?.id} onClose={() => setCurrentView('DASHBOARD')} />;

      case 'KNOWLEDGE_HUB':
        return (
          <KTNavShell user={user} onBack={() => setCurrentView('DASHBOARD')}>
            <div className="flex-1 flex flex-col h-full overflow-hidden">
              <KTViewport user={user} />
            </div>
          </KTNavShell>
        );

      default:
        return <Dashboard user={user} onLogout={handleLogout} onStartQuiz={handleStartQuiz} />;
    }
  };

  return (
    <AppLayout
      currentView={currentView}
      onChangeView={setCurrentView}
      onLogout={handleLogout}
      user={user}
      showSidebar={user && !['LOGIN', 'QUIZ', 'QUIZ_RESULT', 'FORGOT_PASSWORD', 'RESET_PASSWORD', 'PUBLIC_PROFILE', 'KNOWLEDGE_HUB'].includes(currentView)}
      onOpenAIPath={() => setShowAIPath(true)}
      onOpenAIQuiz={() => setShowAIQuiz(true)}
    >
      <AnimatePresence mode="wait" key="view-animator">
        <motion.div
          key={currentView}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="h-full w-full"
        >
          {renderView()}
        </motion.div>
      </AnimatePresence>

      <AnimatePresence key="modal-animator">
        {showAIPath && <AILearningPath onClose={() => setShowAIPath(false)} />}
        {showAIQuiz && (
          <AIQuizGenerator
            onClose={() => setShowAIQuiz(false)}
            onImport={(questions, topic) => {
              toast('success', `${questions.length} AI questions ready to import for topic: ${topic}`);
            }}
            groupId={user?.group_id}
          />
        )}
      </AnimatePresence>
    </AppLayout>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
