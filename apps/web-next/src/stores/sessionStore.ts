'use client';

/**
 * Session + active-assessment state (Phase 4 frontend rebuild).
 *
 * Replaces the React state that lived inside the old single-page state
 * machine (app/page.tsx). Routes are now real URLs; state that must survive
 * navigation between them (who am I, which assessment is running) lives here.
 */

import { create } from 'zustand';
import ApiService from '@/services/ApiService';

export interface SessionUser {
  id: number;
  full_name: string;
  email?: string;
  role: 'Member' | 'GroupAdmin' | 'Mentor' | 'LDAdmin' | 'PlatformAdmin' | string;
  group_id?: number;
  group_name?: string;
  organization_id?: number;
  [key: string]: unknown;
}

interface QuizRun {
  bank: Record<string, unknown> | null;
  questions: Array<Record<string, unknown>>;
  result: Record<string, unknown> | null;
}

interface SessionState {
  user: SessionUser | null;
  hydrated: boolean;
  quiz: QuizRun;

  hydrate: () => Promise<SessionUser | null>;
  setUser: (u: SessionUser | null) => void;
  logout: () => void;

  startQuiz: (bank: Record<string, unknown>, questions: Array<Record<string, unknown>>) => void;
  finishQuiz: (result: Record<string, unknown>) => void;
  clearQuiz: () => void;
}

/** Role → landing route (the old LOGIN-success redirect, now URL-based). */
export function landingRouteFor(user: SessionUser | null): string {
  if (!user) return '/login';
  if (user.role === 'LDAdmin') return '/admin';
  if (user.role === 'Mentor') return '/mentor';
  if (user.role === 'GroupAdmin') return '/group-admin';
  return '/dashboard';
}

export const useSessionStore = create<SessionState>((set, get) => ({
  user: null,
  hydrated: false,
  quiz: { bank: null, questions: [], result: null },

  hydrate: async () => {
    // Cookie-based session: ask the API who we are. 401 = not logged in.
    try {
      const me = await ApiService.getMe();
      if (me && me.success) {
        set({ user: me as unknown as SessionUser, hydrated: true });
        return get().user;
      }
    } catch {
      /* not logged in */
    }
    set({ user: null, hydrated: true });
    return null;
  },

  setUser: (u) => set({ user: u, hydrated: true }),

  logout: () => {
    ApiService.logout();
    set({ user: null, quiz: { bank: null, questions: [], result: null } });
  },

  startQuiz: (bank, questions) =>
    set({ quiz: { bank, questions, result: null } }),

  finishQuiz: (result) =>
    set((s) => ({ quiz: { ...s.quiz, result } })),

  clearQuiz: () => set({ quiz: { bank: null, questions: [], result: null } }),
}));
