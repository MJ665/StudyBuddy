'use client';
// ============================================================
// KT Gate Store — Zustand
// ============================================================
// Manages the Access Key gateway state (before user is JWT-authed
// or when an external user uses a passkey to access KT chat).
// Persisted to sessionStorage so it survives page refreshes
// within the same browser session.

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { KTKeyVerification } from '@/types/kt';

export type GateState = 'idle' | 'verifying' | 'verified' | 'error';

interface KTGateStore {
  // ─── State ───────────────────────────────────────────────────────────────
  gateState: GateState;
  rawKey: string;               // The key entered by the user (cleared after session creation)
  verification: KTKeyVerification | null;
  sessionId: string | null;     // Created after key verification succeeds
  errorMessage: string;

  // NEW: Scope state
  scopedProjectIds: string[];
  scopedCompanyId: string | null;
  scopeLabel: string | null;
  accessibleDocIds: string[];
  authMode: 'jwt' | 'key' | null;

  // ─── Actions ─────────────────────────────────────────────────────────────
  setRawKey: (key: string) => void;
  setGateState: (state: GateState) => void;
  setVerification: (v: KTKeyVerification) => void;
  setSessionId: (id: string) => void;
  setError: (msg: string) => void;
  clearKey: () => void;         // Wipe raw key from memory after session creation
  resetGate: () => void;        // Full reset (e.g. on logout)
  setScopeFromKey: (scope: any) => void;
  setAccessibleDocs: (docIds: string[]) => void;
  setAuthMode: (mode: 'jwt' | 'key' | null) => void;
  isDocAccessible: (docId: string) => boolean;
}

export const useKTGateStore = create<KTGateStore>()(
  persist(
    (set, get) => ({
      gateState: 'idle',
      rawKey: '',
      verification: null,
      sessionId: null,
      errorMessage: '',
      scopedProjectIds: [],
      scopedCompanyId: null,
      scopeLabel: null,
      accessibleDocIds: [],
      authMode: null,

      setRawKey: (key) => set({ rawKey: key, errorMessage: '' }),
      setGateState: (state) => set({ gateState: state }),
      setVerification: (v) =>
        set({ verification: v, gateState: v.valid ? 'verified' : 'error' }),
      setSessionId: (id) => set({ sessionId: id }),
      setError: (msg) => set({ errorMessage: msg, gateState: 'error' }),
      clearKey: () => set({ rawKey: '' }),
      setScopeFromKey: (scope) => set({ 
        scopedProjectIds: scope.project_ids,
        scopedCompanyId: scope.company_id,
        scopeLabel: scope.scope_label,
        authMode: 'key' 
      }),
      setAccessibleDocs: (docIds) => set({ accessibleDocIds: docIds }),
      setAuthMode: (mode) => set({ authMode: mode }),
      isDocAccessible: (docId) => get().accessibleDocIds.includes(docId) || get().authMode === 'jwt',
      resetGate: () =>
        set({
          gateState: 'idle',
          rawKey: '',
          verification: null,
          sessionId: null,
          errorMessage: '',
          scopedProjectIds: [],
          scopedCompanyId: null,
          scopeLabel: null,
          accessibleDocIds: [],
          authMode: null,
        }),
    }),
    {
      name: 'kt-gate-store',
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' ? sessionStorage : localStorage
      ),
      // Never persist the raw key itself — security hardening
      partialize: (state) => ({
        verification: state.verification,
        sessionId: state.sessionId,
        authMode: state.authMode,
        scopedProjectIds: state.scopedProjectIds,
        scopedCompanyId: state.scopedCompanyId,
        scopeLabel: state.scopeLabel,
        accessibleDocIds: state.accessibleDocIds,
        gateState:
          state.gateState === 'verified' ? ('verified' as GateState) : ('idle' as GateState),
      }),
    }
  )
);
