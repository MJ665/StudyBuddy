'use client';
// ============================================================
// KT Navigation Store — Zustand
// ============================================================
// Manages the Company → Project → Document → Sprint hierarchy
// that underpins the KT module's navigation model.
// The nav state IS persisted to localStorage so the user stays
// in the last project they were viewing.

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { KTCompany, KTProject } from '@/types/kt';

export type KTView =
  | 'hub'           // Top-level KT landing: company selector
  | 'projects'      // Project list within a company
  | 'documents'     // Document list within a project
  | 'document'      // Single document detail
  | 'graph'         // Force-directed knowledge graph
  | 'analytics'     // Project/company analytics dashboard
  | 'handoff'       // Handoff engine
  | 'chat'          // AI chat interface
  | 'create'        // Document creation wizard
  | 'keys'          // Access keys management
  | 'discovery'     // Knowledge gap discovery
  | 'mentor-inbox'  // Mentor document review inbox
  | 'key-scoped-projects' // Access key scoped projects view
  | 'unanswered';   // Unanswered AI queries

interface KTNavStore {
  // ─── Hierarchy ────────────────────────────────────────────────────────────
  selectedCompany: KTCompany | null;
  selectedProject: KTProject | null;
  selectedDocId: string | null;
  selectedSprint: string | null;
  sprintList: string[];

  // ─── View ─────────────────────────────────────────────────────────────────
  currentView: KTView;

  // ─── Filters ──────────────────────────────────────────────────────────────
  docStatusFilter: string;       // '' = all
  docTypeFilter: string;         // '' = all
  docSearchQuery: string;

  // ─── Actions ──────────────────────────────────────────────────────────────
  selectCompany: (company: KTCompany) => void;
  selectProject: (project: KTProject) => void;
  selectDoc: (docId: string) => void;
  selectSprint: (sprint: string | null) => void;
  setSprintList: (sprints: string[]) => void;
  setView: (view: KTView) => void;
  setDocStatusFilter: (status: string) => void;
  setDocTypeFilter: (type: string) => void;
  setDocSearchQuery: (query: string) => void;
  clearProject: () => void;
  clearCompany: () => void;
  reset: () => void;
}

const DEFAULT_STATE = {
  selectedCompany: null,
  selectedProject: null,
  selectedDocId: null,
  selectedSprint: null,
  sprintList: [],
  currentView: 'hub' as KTView,
  docStatusFilter: '',
  docTypeFilter: '',
  docSearchQuery: '',
};

export const useKTNavStore = create<KTNavStore>()(
  persist(
    (set) => ({
      ...DEFAULT_STATE,

      selectCompany: (company) =>
        set({
          selectedCompany: company,
          selectedProject: null,
          selectedDocId: null,
          currentView: 'projects',
          docStatusFilter: '',
          docTypeFilter: '',
          docSearchQuery: '',
        }),

      selectProject: (project) =>
        set({
          selectedProject: project,
          selectedDocId: null,
          currentView: 'documents',
          docStatusFilter: '',
          docSearchQuery: '',
        }),

      selectDoc: (docId) =>
        set({ selectedDocId: docId, currentView: 'document' }),

      selectSprint: (sprint) => set({ selectedSprint: sprint }),

      setSprintList: (sprints) => set({ sprintList: sprints }),

      setView: (view) => set({ currentView: view }),

      setDocStatusFilter: (status) => set({ docStatusFilter: status }),
      setDocTypeFilter: (type) => set({ docTypeFilter: type }),
      setDocSearchQuery: (query) => set({ docSearchQuery: query }),

      clearProject: () =>
        set({
          selectedProject: null,
          selectedDocId: null,
          currentView: 'projects',
        }),

      clearCompany: () =>
        set({
          selectedCompany: null,
          selectedProject: null,
          selectedDocId: null,
          currentView: 'hub',
        }),

      reset: () => set(DEFAULT_STATE),
    }),
    {
      name: 'kt-nav-store',
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' ? localStorage : sessionStorage
      ),
    }
  )
);
