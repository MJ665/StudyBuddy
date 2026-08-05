import React, { ReactNode, useEffect, useState } from 'react';
import { Sidebar } from './Sidebar';
import { BottomNav } from './BottomNav';
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
      {/* ── Branding top bar (mobile + tablet, below lg) ── */}
      {showSidebar && user && (
        <header className="lg:hidden fixed top-0 inset-x-0 z-40 h-14 flex items-center gap-3 px-4 bg-[var(--color-surface-container-low)] border-b border-[var(--color-surface-bright)] print:hidden">
          <img src="/images/logo.png" alt="" className="w-7 h-7 rounded-lg object-cover" />
          <span className="text-base font-black text-white">StudyBuddy</span>
        </header>
      )}

      {/* ── Sidebar: desktop only (lg+); mobile/tablet use the bottom nav ── */}
      {showSidebar && user && (
        <div className="hidden lg:block shrink-0">
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

      <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden print:overflow-visible relative custom-scrollbar pt-14 lg:pt-0 pb-16 lg:pb-0">
        {children}
        <div className="pointer-events-none fixed bottom-2 right-3 z-40 print:hidden opacity-50 hidden lg:block">
          <PoweredByStudyBuddy />
        </div>
      </main>

      {/* ── Bottom navigation (mobile + tablet, below lg) ── */}
      {showSidebar && user && (
        <BottomNav
          currentView={currentView}
          onChangeView={onChangeView}
          user={user}
          onLogout={onLogout}
        />
      )}
    </div>
  );
}
