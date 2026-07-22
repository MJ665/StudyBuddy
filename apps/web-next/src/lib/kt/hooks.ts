'use client';
// ============================================================
// KT React Query Hooks
// ============================================================
// Centralised data-fetching hooks for the KT module.
// All hooks use ApiService as the transport layer.
// All cache keys come from ktQueryKeys to guarantee consistency.

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ApiService from '@/services/ApiService';
import { ktQueryKeys } from '@/lib/kt/queryKeys';
import type {
  KTCompany,
  KTProject,
  KTDocument,
  KTAccessKey,
  KTKeyWithRaw,
  KTHandoff,
  KTNotification,
  KTGap,
  KTCompanyInsights,
  KTProjectInsights,
  KTGraphData,
  HandoffGapAnalysis,
} from '@/types/kt';

// ─── Companies ───────────────────────────────────────────────────────────────

export function useKTCompanies() {
  return useQuery<KTCompany[]>({
    queryKey: ktQueryKeys.companies(),
    queryFn: () => ApiService.getKTCompanies(),
  });
}

// ─── Projects ────────────────────────────────────────────────────────────────

export function useKTProjects(companyId?: string) {
  return useQuery<KTProject[]>({
    queryKey: ktQueryKeys.projects(companyId),
    queryFn: () => ApiService.getKTProjects(companyId),
    enabled: true,
  });
}

export function useKTProjectDetail(projectId: string) {
  return useQuery<KTProject>({
    queryKey: ktQueryKeys.projectDetail(projectId),
    queryFn: () => ApiService.getKTProjectDetails(projectId),
    enabled: !!projectId,
  });
}

// ─── Documents ───────────────────────────────────────────────────────────────

export function useKTDocuments(filters: {
  project_id?: string;
  status?: string;
  doc_type?: string;
  sprint?: string;
  search?: string;
  page?: number;
}) {
  return useQuery<KTDocument[]>({
    queryKey: ktQueryKeys.documents(filters),
    queryFn: () => ApiService.getKTDocuments(filters),
    enabled: true,
  });
}

export function useKTDocument(docId: string) {
  return useQuery<KTDocument>({
    queryKey: ktQueryKeys.document(docId),
    queryFn: () => ApiService.getKTDocument(docId),
    enabled: !!docId,
  });
}

export function useKTDocumentVersions(docId: string) {
  return useQuery({
    queryKey: ktQueryKeys.documentVersions(docId),
    queryFn: () => ApiService.getKTDocumentVersions(docId),
    enabled: !!docId,
  });
}

export function useKTDocumentAttachments(docId: string) {
  return useQuery({
    queryKey: ktQueryKeys.documentAttachments(docId),
    queryFn: () => ApiService.getKTDocumentAttachments(docId),
    enabled: !!docId,
  });
}

// ─── Document Mutations ──────────────────────────────────────────────────────

export function useCreateKTDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => ApiService.createKTDocument(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kt', 'documents'] });
    },
  });
}

export function useUpdateKTDocument(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => ApiService.updateKTDocument(docId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.document(docId) });
      qc.invalidateQueries({ queryKey: ['kt', 'documents'] });
    },
  });
}

export function useSubmitKTDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ docId, mentorId }: { docId: string; mentorId?: number }) =>
      ApiService.submitKTDocument(docId, { mentor_id: mentorId }),
    onSuccess: (_data, { docId }) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.document(docId) });
      qc.invalidateQueries({ queryKey: ['kt', 'documents'] });
      qc.invalidateQueries({ queryKey: ktQueryKeys.mentorInbox() });
    },
  });
}

export function useReviewKTDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      docId,
      action,
      comment,
    }: {
      docId: string;
      action: 'approved' | 'rejected' | 'requested_changes';
      comment?: string;
    }) => ApiService.reviewKTDocument(docId, action, comment),
    onSuccess: (_data, { docId }) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.document(docId) });
      qc.invalidateQueries({ queryKey: ['kt', 'documents'] });
      qc.invalidateQueries({ queryKey: ktQueryKeys.mentorInbox() });
    },
  });
}

export function useTriggerKTIngestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => ApiService.triggerKTIngestion(docId),
    onSuccess: (_data, docId) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.document(docId) });
    },
  });
}

export function useEndorseKTDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ docId, comment }: { docId: string; comment?: string }) =>
      ApiService.endorseKTDocument(docId, comment),
    onSuccess: (_data, { docId }) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.document(docId) });
    },
  });
}

// ─── Access Keys ─────────────────────────────────────────────────────────────

export function useKTKeys(companyId?: string, activeOnly: boolean = true) {
  return useQuery<KTAccessKey[]>({
    queryKey: ktQueryKeys.keys(companyId),
    queryFn: () => ApiService.getKTKeys(companyId, activeOnly),
  });
}

export function useGenerateKTKey() {
  const qc = useQueryClient();
  return useMutation<KTKeyWithRaw, Error, Parameters<typeof ApiService.generateKTKey>[0]>({
    mutationFn: (data) => ApiService.generateKTKey(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kt', 'keys'] });
    },
  });
}

export function useRevokeKTKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => ApiService.revokeKTKey(keyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kt', 'keys'] });
    },
  });
}

export function useVerifyKTKey() {
  return useMutation({
    mutationFn: (rawKey: string) => ApiService.verifyKTKey(rawKey),
  });
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export function useStartKTChatSession() {
  return useMutation({
    mutationFn: ({
      projectIds,
      rawKey,
      companyId,
    }: {
      projectIds: string[];
      rawKey?: string;
      companyId?: string;
    }) => ApiService.startKTChatSession(projectIds, rawKey, companyId),
  });
}

export function useAskKTQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      message,
      rawKey,
    }: {
      sessionId: string;
      message: string;
      rawKey?: string;
    }) => ApiService.askKTQuestion(sessionId, message, rawKey),
    onSuccess: (_data, { sessionId }) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.chatHistory(sessionId) });
    },
  });
}

export function useSubmitChatFeedback() {
  return useMutation({
    mutationFn: ({
      messageId,
      feedback,
      note,
    }: {
      messageId: string;
      feedback: 1 | -1;
      note?: string;
    }) => ApiService.submitChatFeedback(messageId, feedback, note),
  });
}

// ─── Knowledge Graph ─────────────────────────────────────────────────────────

export function useKTGraphData(projectIds: string[], rawKey?: string) {
  return useQuery<KTGraphData>({
    queryKey: ktQueryKeys.graphData(projectIds),
    queryFn: () => ApiService.getKTGraphData(projectIds, rawKey),
    enabled: projectIds.length > 0,
    staleTime: 5 * 60 * 1000, // Graph is expensive — cache for 5 minutes
  });
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export function useKTAnalyticsSummary() {
  return useQuery({
    queryKey: ktQueryKeys.analyticsSummary(),
    queryFn: () => ApiService.getKTAnalyticsSummary(),
  });
}

export function useKTCompanyAnalytics(companyId?: string) {
  return useQuery<KTCompanyInsights>({
    queryKey: ktQueryKeys.companyAnalytics(companyId),
    queryFn: () => ApiService.getKTCompanyAnalytics(companyId),
  });
}

export function useKTProjectAnalytics(projectId: string) {
  return useQuery<KTProjectInsights>({
    queryKey: ktQueryKeys.projectAnalytics(projectId),
    queryFn: () => ApiService.getKTProjectAnalytics(projectId),
    enabled: !!projectId,
  });
}

// ─── Knowledge Gaps ──────────────────────────────────────────────────────────

export function useKTGaps(resolved: boolean = false, companyId?: string) {
  return useQuery<KTGap[]>({
    queryKey: ktQueryKeys.gaps(resolved, companyId),
    queryFn: () => ApiService.getKTGaps(resolved),
  });
}

// ─── Handoffs ────────────────────────────────────────────────────────────────

export function useKTHandoffs() {
  return useQuery<KTHandoff[]>({
    queryKey: ktQueryKeys.handoffs(),
    queryFn: () => ApiService.listKTHandoffs(),
  });
}

export function useKTHandoff(handoffId: string) {
  return useQuery<KTHandoff>({
    queryKey: ktQueryKeys.handoff(handoffId),
    queryFn: () => ApiService.getKTHandoff(handoffId),
    enabled: !!handoffId,
  });
}

export function useHandoffGaps(departingUserId: number, companyId: string) {
  return useQuery<HandoffGapAnalysis>({
    queryKey: ktQueryKeys.handoffGaps(departingUserId, companyId),
    queryFn: () => ApiService.analyze_handoff_pre(departingUserId, companyId),
    enabled: !!departingUserId && !!companyId,
  });
}

export function useInitiateHandoff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof ApiService.initiateKTHandoff>[0]) =>
      ApiService.initiateKTHandoff(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.handoffs() });
    },
  });
}

export function useUpdateHandoffChecklist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      handoffId,
      itemIndex,
      done,
    }: {
      handoffId: string;
      itemIndex: number;
      done: boolean;
    }) => ApiService.updateHandoffChecklist(handoffId, itemIndex, done),
    onSuccess: (_data, { handoffId }) => {
      qc.invalidateQueries({ queryKey: ktQueryKeys.handoff(handoffId) });
      qc.invalidateQueries({ queryKey: ktQueryKeys.handoffs() });
    },
  });
}

// ─── Notifications ───────────────────────────────────────────────────────────

export function useKTNotifications(unreadOnly: boolean = false) {
  return useQuery<KTNotification[]>({
    queryKey: ktQueryKeys.notifications(unreadOnly),
    queryFn: () => ApiService.getKTNotifications(unreadOnly),
    refetchInterval: 60 * 1000, // Poll every minute
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notifId: string) => ApiService.markKTNotificationRead(notifId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kt', 'notifications'] });
    },
  });
}

// ─── Mentor Inbox ─────────────────────────────────────────────────────────────

export function useMentorInbox(page: number = 1) {
  return useQuery({
    queryKey: ktQueryKeys.mentorInbox(page),
    queryFn: () => ApiService.getMentorInbox(page),
  });
}
