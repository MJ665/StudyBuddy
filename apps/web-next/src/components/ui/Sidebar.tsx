import React, { useState, useEffect } from 'react';
import { LogOut, Map, Sparkles, Flame } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ApiService from '../../services/ApiService';
import { isGroupAdminPlus, isMentorPlus, isLDAdminPlus } from '../../lib/kt/permissions';

interface SidebarProps {
  currentView: string;
  onChangeView: (view: any) => void;
  onLogout: () => void;
  user: any;
  onOpenAIPath?: () => void;
  onOpenAIQuiz?: () => void;
  onNavigate?: () => void; // closes the mobile drawer after a selection
}

export function Sidebar({ currentView, onChangeView, onLogout, user, onOpenAIPath, onOpenAIQuiz, onNavigate }: SidebarProps) {
  const isLdAdmin = isLDAdminPlus(user?.role || 'Member');
  const isMentor = isMentorPlus(user?.role || 'Member');
  const isGroupAdmin = isGroupAdminPlus(user?.role || 'Member');
  const isPlatformAdmin = user?.role === 'PlatformAdmin';
  const isAdmin = isGroupAdmin || isMentor || isLdAdmin;
  const [accuracy, setAccuracy] = useState<number | null>(null);
  const [streakCount, setStreakCount] = useState<number>(0);
  const [activeTracks, setActiveTracks] = useState<any[]>([]);

  // Load average accuracy and active tracks
  useEffect(() => {
    ApiService.getMyStats()
      .then((res: any) => {
        if (res?.overall_accuracy !== undefined) {
          setAccuracy(res.overall_accuracy);
        } else if (res?.banks_attempted?.length > 0) {
          const totalScore = res.banks_attempted.reduce((s: number, b: any) => s + (b.score || 0), 0);
          const totalQ = res.banks_attempted.reduce((s: number, b: any) => s + (b.total || 0), 0);
          setAccuracy(totalQ > 0 ? Math.round((totalScore / totalQ) * 100) : 0);
        }
        if (res?.streak_count !== undefined) setStreakCount(res.streak_count);
      })
      .catch(() => { /* ignore */ });

    // 2. Active Tracks (Courses)
    if (user?.group_id) {
      ApiService.getCourses(user.group_id)
        .then(courses => setActiveTracks(courses.slice(0, 4)))
        .catch(err => console.error('Failed to load courses', err));
    }
  }, [user?.group_id]);

  const navItems = [
    { icon: 'dashboard',     label: 'Dashboard',       view: 'DASHBOARD' },
    { icon: 'hub',           label: 'Knowledge Hub',   view: 'KNOWLEDGE_HUB' },
    { icon: 'assignment',    label: 'Assignments',     view: 'ASSIGNMENTS' },
    { icon: 'history',       label: 'Attempt History', view: 'ATTEMPT_HISTORY' },
    { icon: 'library_books', label: 'Library',         view: 'LIBRARY' },
    { icon: 'forum',         label: 'Discussions',     view: 'DISCUSSIONS' },
    { icon: 'person',        label: 'My Profile',      view: 'PROFILE' },
    { icon: 'folder_open',   label: 'Resources',       view: 'RESOURCES' },
    ...(isGroupAdmin ? [
      { icon: 'settings', label: 'Group Admin',   view: 'ADMIN' }
    ] : []),
    ...(isMentor     ? [{ icon: 'school',   label: 'Mentor Hub',    view: 'MENTOR' }] : []),
    ...(isLdAdmin    ? [{ icon: 'shield',   label: 'L&D Ecosystem', view: 'LD_ADMIN' }] : []),
    // Route-based screens (full-page navigation) rather than view-state.
    ...(isMentor        ? [{ icon: 'quiz',    label: 'Exams',          href: '/exams' }] : []),
    ...(isPlatformAdmin ? [{ icon: 'shield',  label: 'Platform Admin', href: '/platform' }] : []),
  ];

  return (
    <div className="w-64 h-full bg-surface-container-low border-r border-[var(--color-surface-bright)] flex flex-col py-8 z-50 shrink-0 print:hidden">
      {/* ─── App Branding ──────────────────────────────────────── */}
      <div className="px-6 mb-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg overflow-hidden shrink-0">
            <img src="/images/logo.png" alt="StudyBuddy Logo" className="w-full h-full object-cover rounded-xl" />
          </div>
          <div>
            <p className="text-lg font-black text-white leading-tight">StudyBuddy</p>
            <p className="text-[10px] text-[var(--color-on-surface-variant)] uppercase tracking-widest font-bold">AI Assessment</p>
          </div>
        </div>
      </div>
      
      {/* ─── Navigation ────────────────────────────────────────── */}
      <nav className="flex flex-col gap-1 w-full px-4">
        {navItems.map((item: { icon: string; label: string; view?: string; href?: string }) => (
          <SidebarItem
            key={item.label}
            icon={item.icon}
            label={item.label}
            active={item.view ? currentView === item.view : false}
            onClick={() => {
              onNavigate?.();
              item.href ? (window.location.href = item.href) : item.view && onChangeView(item.view);
            }}
          />
        ))}
      </nav>

      {/* ─── Active Tracks ─────────────────────────────────────── */}
      <div className="px-6 mt-8">
        <p className="text-[10px] uppercase tracking-widest font-bold text-slate-500 mb-3">Active Tracks</p>
        <div className="space-y-2.5">
          {activeTracks.map((course, i) => (
            <div key={course.id || i} className="flex items-center gap-2.5">
              <div className={`w-2 h-2 rounded-full ${
                i % 3 === 0 ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]' :
                i % 3 === 1 ? 'bg-indigo-400 shadow-[0_0_6px_rgba(129,140,248,0.5)]' :
                'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]'
              }`} />
              <span className="text-xs text-slate-400 font-medium truncate max-w-[140px]">{course.name}</span>
            </div>
          ))}
          {activeTracks.length === 0 && (
            <p className="text-[10px] text-slate-600 italic">No tracks active</p>
          )}
        </div>

      {/* ─── AI Tools Quick Access ─────────────────────────────── */}
      {currentView === 'DASHBOARD' && (
        <div className="px-4 mt-6">
          <p className="text-[10px] uppercase tracking-widest font-bold text-slate-500 mb-2 px-2">AI Tools</p>
          <div className="space-y-1">
            <button
              onClick={onOpenAIPath}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 transition-all font-semibold"
            >
              <Map size={16} className="text-purple-400" />
              Learning Path
            </button>
            <button
              onClick={onOpenAIQuiz}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 transition-all font-semibold"
            >
              <Sparkles size={16} className="text-indigo-400" />
              AI Quiz Builder
            </button>
          </div>
        </div>
      )}
      </div>

      {/* ─── Bottom Section: User + Accuracy ───────────────────── */}
      <div className="mt-auto w-full px-4 pt-8 border-t border-[var(--color-surface-bright)]">
        {/* Accuracy Mini Widget — PRD Section A */}
        {accuracy !== null && (
          <div className="mx-2 mb-4 p-3 bg-surface-container rounded-xl border border-[var(--color-surface-bright)]">
            <p className="text-[10px] uppercase tracking-widest font-bold text-slate-500 mb-1">Average Accuracy</p>
            <p className={`text-2xl font-black ${accuracy >= 70 ? 'text-emerald-400' : accuracy >= 40 ? 'text-amber-400' : 'text-rose-400'}`}>
              {accuracy}%
            </p>
            {/* Progress bar */}
            <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${accuracy}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
                className={`h-full rounded-full ${accuracy >= 70 ? 'bg-emerald-400' : accuracy >= 40 ? 'bg-amber-400' : 'bg-rose-400'}`}
              />
            </div>
          </div>
        )}

        {/* User Card */}
        <button 
          onClick={() => onChangeView('PROFILE')}
          className="w-full text-left flex items-center gap-3 p-3 mb-4 bg-surface-container hover:bg-surface-bright rounded-xl border border-[var(--color-surface-bright)] transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-full bg-[var(--color-brand-primary)] flex items-center justify-center text-[var(--color-surface-dim)] font-black text-lg shadow-lg group-hover:scale-105 transition-transform">
            {user?.full_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-[var(--color-on-surface)] truncate group-hover:text-indigo-400 transition-colors">{user?.full_name}</p>
            <p className="text-[10px] uppercase text-[var(--color-brand-primary-container)] font-black truncate">{user?.role}</p>
          </div>
        </button>
        
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 p-3 text-rose-400 hover:bg-rose-950/30 rounded-xl transition-colors font-bold border border-transparent hover:border-rose-900/50"
        >
          <LogOut size={16} /> Logout
        </button>

        <button
          onClick={async () => {
            if(confirm('Are you sure you want to sign out of all devices? This will invalidate all your active sessions.')) {
              try {
                await ApiService.logoutAll();
                onLogout();
              } catch(e) {
                console.error(e);
              }
            }
          }}
          className="w-full flex items-center justify-center gap-2 p-3 mt-1 text-slate-500 hover:text-rose-400 hover:bg-rose-950/20 rounded-xl transition-colors text-xs font-semibold"
        >
          <LogOut size={14} /> Sign out of all devices
        </button>
      </div>
    </div>
  );
}

const SidebarItem: React.FC<{ icon: string; label: string; active: boolean; onClick: () => void }> = ({ icon, label, active, onClick }) => {
  return (
    <button
      onClick={onClick}
      className={`relative flex items-center gap-3 px-4 py-3 rounded-xl transition-all w-full text-left font-semibold outline-none
        ${active 
          ? 'text-indigo-400 font-bold border-r-4 border-indigo-400 bg-indigo-500/10' 
          : 'text-slate-400 hover:text-white hover:bg-white/5 border-r-4 border-transparent'
        }
      `}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>{icon}</span>
      <span>{label}</span>
      {active && (
        <motion.div
          layoutId="sidebar-active"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-400 rounded-r-full pointer-events-none"
          initial={false}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
      )}
    </button>
  );
};
