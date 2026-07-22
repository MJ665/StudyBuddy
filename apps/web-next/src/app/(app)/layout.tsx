'use client';

/**
 * Authenticated area layout (Phase 4).
 *
 * Every page under (app) gets: session hydration (cookie → getMe), redirect
 * to /login when anonymous, and the existing AppLayout/Sidebar chrome. The
 * `onChangeView` adapter translates legacy view names into router.push so
 * Sidebar/AppLayout keep working unchanged during the migration.
 */

import React, { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence } from 'motion/react';

import { AppLayout } from '@/components/ui/AppLayout';
import AILearningPath from '@/components/dashboard/AILearningPath';
import AIQuizGenerator from '@/components/dashboard/AIQuizGenerator';
import { ToastProvider, useToast } from '@/components/ui/Toast';
import { VIEW_TO_ROUTE, viewForPath } from '@/lib/viewRoutes';
import { useSessionStore } from '@/stores/sessionStore';

// Full-bleed experiences that render their own chrome (no sidebar).
const NO_SIDEBAR_PREFIXES = ['/assessment/run', '/assessment/result', '/kt'];

function AppAreaInner({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { toast } = useToast();
  const { user, hydrated, hydrate, logout } = useSessionStore();
  const [showAIPath, setShowAIPath] = useState(false);
  const [showAIQuiz, setShowAIQuiz] = useState(false);

  useEffect(() => {
    if (!hydrated) void hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (hydrated && !user) router.replace('/login');
  }, [hydrated, user, router]);

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) return null; // redirecting

  const handleChangeView = (view: string) => {
    const route = VIEW_TO_ROUTE[view];
    if (route) router.push(route);
    else toast('error', `Unknown destination: ${view}`);
  };

  const handleLogout = () => {
    logout();
    router.replace('/login');
  };

  const showSidebar = !NO_SIDEBAR_PREFIXES.some((p) => pathname.startsWith(p));

  return (
    <AppLayout
      currentView={viewForPath(pathname)}
      onChangeView={handleChangeView}
      onLogout={handleLogout}
      user={user}
      showSidebar={showSidebar}
      onOpenAIPath={() => setShowAIPath(true)}
      onOpenAIQuiz={() => setShowAIQuiz(true)}
    >
      {children}

      <AnimatePresence key="modal-animator">
        {showAIPath && <AILearningPath onClose={() => setShowAIPath(false)} />}
        {showAIQuiz && (
          <AIQuizGenerator
            onClose={() => setShowAIQuiz(false)}
            onImport={(questions: unknown[], topic: string) => {
              toast('success', `${questions.length} AI questions ready to import for topic: ${topic}`);
            }}
            groupId={user?.group_id}
          />
        )}
      </AnimatePresence>
    </AppLayout>
  );
}

export default function AppAreaLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <AppAreaInner>{children}</AppAreaInner>
    </ToastProvider>
  );
}
