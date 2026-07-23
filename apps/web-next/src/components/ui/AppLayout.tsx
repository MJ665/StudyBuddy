import React, { ReactNode, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { AnimatePresence } from 'motion/react';
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
      {showSidebar && user && (
        <Sidebar
          currentView={currentView}
          onChangeView={onChangeView}
          onLogout={onLogout}
          user={user}
          onOpenAIPath={onOpenAIPath}
          onOpenAIQuiz={onOpenAIQuiz}
        />
      )}

      <main className="flex-1 overflow-y-auto print:overflow-visible relative custom-scrollbar">
        {children}
        <div className="pointer-events-none fixed bottom-2 right-3 z-40 print:hidden opacity-50">
          <PoweredByStudyBuddy />
        </div>
      </main>
    </div>
  );
}
