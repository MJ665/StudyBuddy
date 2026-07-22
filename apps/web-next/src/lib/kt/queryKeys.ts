// ============================================================
// KT Query Keys — React Query / TanStack Query
// ============================================================
// Centralised query key factory for all KT data fetching.
// Collocating keys prevents cache invalidation bugs across components.

export const ktQueryKeys = {
  // ─── Companies ─────────────────────────────────────────────────────────────
  companies: () => ['kt', 'companies'] as const,
  company: (id: string) => ['kt', 'company', id] as const,

  // ─── Projects ──────────────────────────────────────────────────────────────
  projects: (companyId?: string) => ['kt', 'projects', companyId ?? 'all'] as const,
  projectDetail: (projectId: string) => ['kt', 'project', projectId] as const,
  projectAnalytics: (projectId: string) => ['kt', 'analytics', 'project', projectId] as const,
  projectTimeline: (projectId: string) => ['kt', 'timeline', projectId] as const,

  // ─── Documents ─────────────────────────────────────────────────────────────
  documents: (filters: Record<string, string | number | undefined>) =>
    ['kt', 'documents', filters] as const,
  document: (docId: string) => ['kt', 'document', docId] as const,
  documentVersions: (docId: string) => ['kt', 'document', docId, 'versions'] as const,
  documentAttachments: (docId: string) => ['kt', 'document', docId, 'attachments'] as const,
  ingestionStatus: (docId: string) => ['kt', 'document', docId, 'ingestion'] as const,

  // ─── Access Keys ───────────────────────────────────────────────────────────
  keys: (companyId?: string) => ['kt', 'keys', companyId ?? 'all'] as const,

  // ─── Chat ──────────────────────────────────────────────────────────────────
  chatHistory: (sessionId: string) => ['kt', 'chat', sessionId, 'messages'] as const,

  // ─── Handoffs ──────────────────────────────────────────────────────────────
  handoffs: () => ['kt', 'handoffs'] as const,
  handoff: (id: string) => ['kt', 'handoff', id] as const,
  handoffGaps: (userId: number, companyId: string) =>
    ['kt', 'handoff', 'gaps', userId, companyId] as const,

  // ─── Analytics ─────────────────────────────────────────────────────────────
  analyticsSummary: () => ['kt', 'analytics', 'summary'] as const,
  companyAnalytics: (companyId?: string) => ['kt', 'analytics', 'company', companyId ?? 'all'] as const,
  groupInsights: () => ['kt', 'analytics', 'group'] as const,
  myDocTraction: () => ['kt', 'analytics', 'my-docs'] as const,

  // ─── Knowledge Graph ───────────────────────────────────────────────────────
  graphData: (projectIds: string[]) => ['kt', 'graph', ...projectIds.sort()] as const,
  graphStats: (companyId?: string) => ['kt', 'graph', 'stats', companyId ?? 'all'] as const,

  // ─── Knowledge Gaps ────────────────────────────────────────────────────────
  gaps: (resolved?: boolean, companyId?: string) =>
    ['kt', 'gaps', resolved ?? false, companyId ?? 'all'] as const,

  // ─── Notifications ─────────────────────────────────────────────────────────
  notifications: (unreadOnly?: boolean) =>
    ['kt', 'notifications', unreadOnly ?? false] as const,

  // ─── Mentor Inbox ──────────────────────────────────────────────────────────
  mentorInbox: (page?: number) => ['kt', 'mentor', 'inbox', page ?? 1] as const,
};
