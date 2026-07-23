import React, { ReactNode, useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { PoweredByStudyBuddy } from '../common/Branding';

interface AppLayoutProps {
  children: ReactNode;
  currentView: string;
  onChangeView: (view: any) => void;
  onLogout: () => void;
  user: any;
  showSidebar?: boolean;
  onOpenAIPath?: () => void;
  onOpenAIQuiz?: () => void;
}

export function AppLayout({ children, currentView, onChangeView, onLogout, user, showSidebar = true, onOpenAIPath, onOpenAIQuiz }: AppLayoutProps) {
  const isLdAdmin = user?.role === 'LDAdmin';
  const isMentor = user?.role === 'Mentor';
  const isGroupAdmin = user?.role === 'GroupAdmin' || user?.role === 'Admin';
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Close the mobile drawer whenever the active view changes.
  useEffect(() => { setMobileNavOpen(false); }, [currentView]);

  // Global State RBAC Guarding
  useEffect(() => {
    if (!user) return;
    if (currentView === 'ADMIN' && !isGroupAdmin) onChangeView('DASHBOARD');
    if (currentView === 'MENTOR' && !isMentor) onChangeView('DASHBOARD');
    if (currentView === 'LD_ADMIN' && !isLdAdmin) onChangeView('DASHBOARD');
    if (currentView === 'USER_INTEL' && !isLdAdmin && !isMentor && !isGroupAdmin) onChangeView('DASHBOARD');
    // (EXECUTIVE_REPORT / ORG_SETTINGS guards removed — those state-machine
    // views no longer exist; their routes carry their own role gates.)
  }, [currentView, user, isGroupAdmin, isMentor, isLdAdmin, onChangeView]);

  return (
    <div className="flex h-screen print:h-auto bg-[var(--color-surface-dim)] overflow-hidden print:overflow-visible font-sans text-[var(--color-on-surface)] selection:bg-[var(--color-brand-primary)]/30">
      {/* ── Mobile top bar (below md) — hamburger + branding ── */}
      {showSidebar && user && (
        <header className="md:hidden fixed top-0 inset-x-0 z-40 h-14 flex items-center gap-3 px-4 bg-[var(--color-surface-container-low)] border-b border-[var(--color-surface-bright)] print:hidden">
          <button
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation menu"
            className="p-2 -ml-2 rounded-lg text-slate-300 hover:bg-white/5 active:scale-95 transition"
          >
            <Menu size={22} />
          </button>
          <img src="/images/logo.png" alt="" className="w-7 h-7 rounded-lg object-cover" />
          <span className="text-base font-black text-white">StudyBuddy</span>
        </header>
      )}

      {/* ── Backdrop when the drawer is open (mobile only) ── */}
      {showSidebar && user && mobileNavOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden
        />
      )}

      {/* ── Sidebar: static column on md+, slide-in drawer below md ── */}
      {showSidebar && user && (
        <div
          className={`fixed md:static inset-y-0 left-0 z-50 transition-transform duration-300 md:transition-none
            ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
        >
          <button
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation menu"
            className="md:hidden absolute top-4 right-3 z-10 p-1.5 rounded-lg text-slate-400 hover:bg-white/5"
          >
            <X size={20} />
          </button>
          <Sidebar
            currentView={currentView}
            onChangeView={onChangeView}
            onLogout={onLogout}
            user={user}
            onOpenAIPath={onOpenAIPath}
            onOpenAIQuiz={onOpenAIQuiz}
            onNavigate={() => setMobileNavOpen(false)}
          />
        </div>
      )}

      <main className="flex-1 overflow-y-auto print:overflow-visible relative custom-scrollbar pt-14 md:pt-0">
        {children}
        <div className="pointer-events-none fixed bottom-2 right-3 z-40 print:hidden opacity-50">
          <PoweredByStudyBuddy />
        </div>
      </main>
    </div>
  );
}
