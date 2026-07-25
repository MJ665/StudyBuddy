import { API_BASE, getBaseUrl, AIResponseEnvelope, SystemConfig, UserMe, ConsistencyResult, EngagementDecayResult, CompositeHealthResult, BatchInsights, AiInsightsResult, ExecutiveSummary } from './apiShared';
import { ApiClient2 } from './apiClient2';

/* eslint-disable @typescript-eslint/no-explicit-any */
export class ApiClient3 extends ApiClient2 {
  static async getKTDocument(docId: string, accessKey?: string) {
    const headers = this.getHeaders();
    if (accessKey) headers['X-KT-Key'] = accessKey;
    return this.request(`/kt/documents/${docId}`, { headers });
  }

  static async createKTDocument(data: any) {
    return this.request('/kt/documents', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateKTDocument(docId: string, data: any) {
    return this.request(`/kt/documents/${docId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  static async submitKTDocument(docId: string, data: { mentor_id?: number } = {}) {
    return this.request(`/kt/documents/${docId}/submit`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async reviewKTDocument(docId: string, action: 'approved' | 'rejected' | 'requested_changes', comment?: string) {
    return this.request(`/kt/documents/${docId}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, comment }),
    });
  }

  // CRITICAL: Only call after reviewKTDocument('approved') — triggers ingestion pipeline
  static async triggerKTIngestion(docId: string) {
    return this.request(`/kt/documents/${docId}/feed`, { method: 'POST' });
  }

  static async deprecateKTDocument(docId: string) {
    return this.request(`/kt/documents/${docId}/deprecate`, { method: 'POST' });
  }

  static async deleteKTDocument(docId: string) {
    return this.request(`/kt/documents/${docId}`, { method: 'DELETE' });
  }

  static async endorseKTDocument(docId: string, comment?: string) {
    const params = comment ? `?comment=${encodeURIComponent(comment)}` : '';
    return this.request(`/kt/documents/${docId}/endorse${params}`, { method: 'POST' });
  }

  static async getKTDocumentVersions(docId: string) {
    return this.request(`/kt/documents/${docId}/versions`);
  }

  static async getKTDocumentVersion(docId: string, version: number) {
    return this.request(`/kt/documents/${docId}/versions/${version}`);
  }

  static async getKTIngestionStatus(docId: string) {
    return this.request(`/kt/documents/${docId}/ingestion-status`);
  }

  static async aiSuggestImprovements(docId: string) {
    return this.request(`/kt/documents/${docId}/ai-suggest`, { method: 'POST' });
  }

  // ─── Attachments ──────────────────────────────────────────────────────────

  static async getKTDocumentAttachments(docId: string, accessKey?: string) {
    const headers = this.getHeaders();
    if (accessKey) headers['X-KT-Key'] = accessKey;
    return this.request(`/kt/documents/${docId}/attachments`, { headers });
  }

  static async getKTAttachmentUploadUrl(docId: string, filename: string, contentType: string) {
    return this.request(`/kt/documents/${docId}/attachments/presign`, {
      method: 'POST',
      body: JSON.stringify({ filename, content_type: contentType }),
    });
  }

  static async registerKTAttachment(docId: string, data: any) {
    return this.request(`/kt/documents/${docId}/attachments`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async deleteKTAttachment(attachmentId: string) {
    return this.request(`/kt/attachments/${attachmentId}`, { method: 'DELETE' });
  }

  // ─── Access Keys ──────────────────────────────────────────────────────────

  // Step 1: verify key without consuming a use (shows scope preview)
  static async verifyKTKey(rawKey: string) {
    return this.request('/kt/keys/verify', {
      method: 'POST',
      headers: { ...this.getHeaders(), 'X-KT-Key': rawKey },
    });
  }

  // Step 2: generate session (consumes one use)
  static async startKTChatSession(projectIds: string[], rawKey?: string, companyId?: string) {
    const headers = this.getHeaders();
    if (rawKey) headers['X-KT-Key'] = rawKey;
    return this.request('/kt/chat/session', {
      method: 'POST',
      headers,
      body: JSON.stringify({ project_ids: projectIds, company_id: companyId }),
    });
  }

  static async generateKTKey(data: {
    project_ids: string[];
    company_id?: string;
    scope_label?: string;
    recipient_email?: string;
    recipient_name?: string;
    ttl_days?: number;
    max_uses?: number;
    send_email?: boolean;
    notes?: string;
  }) {
    // Validate: project_ids must be non-empty and contain no null/undefined values
    if (!data.project_ids || data.project_ids.length === 0 || data.project_ids.some(id => !id)) {
      throw new Error('At least one valid project must be selected to generate a key');
    }
    return this.request('/kt/keys/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async getKTKeyScope(rawKey: string) {
    const headers = this.getHeaders();
    headers['X-KT-Key'] = rawKey;
    return this.request('/kt/keys/scope', { headers });
  }

  // ─── Platform Admin (super-admin governance) ────────────────────────────────
  static async platformListOrgs(status?: string) {
    const q = status ? `?status=${status}` : '';
    return this.request(`/platform/organizations${q}`);
  }
  static async platformApproveOrg(orgId: number) {
    return this.request(`/platform/organizations/${orgId}/approve`, { method: 'POST' });
  }
  static async platformSuspendOrg(orgId: number) {
    return this.request(`/platform/organizations/${orgId}/suspend`, { method: 'POST' });
  }
  static async platformReactivateOrg(orgId: number) {
    return this.request(`/platform/organizations/${orgId}/reactivate`, { method: 'POST' });
  }
  static async platformAIUsage(days: number = 30) {
    return this.request(`/platform/ai-usage?days=${days}`);
  }
  static async platformStats() {
    return this.request('/platform/stats');
  }

  // ─── Organization onboarding (public) ──────────────────────────────────────
  static async orgSignup(data: { org_name: string; contact_name: string; contact_email: string }) {
    return this.request('/onboarding/signup', { method: 'POST', body: JSON.stringify(data) });
  }
  static async verifyOnboarding(token: string) {
    return this.request(`/onboarding/verify?token=${encodeURIComponent(token)}`);
  }
  static async completeOnboarding(data: {
    token: string; admin_full_name: string; admin_email: string; admin_password: string;
    brand_name?: string; logo_url?: string; signature_url?: string;
  }) {
    return this.request('/onboarding/complete', { method: 'POST', body: JSON.stringify(data) });
  }

  // ─── Exams (proctored) ──────────────────────────────────────────────────────
  static async createExam(data: {
    title: string; description?: string; bank_id?: number; question_ids?: number[];
    duration_minutes: number; passing_score: number; max_attempts?: number;
    shuffle_questions?: boolean; shuffle_options?: boolean; proctoring_mode?: string; is_published?: boolean;
    recipient_emails?: string[];
  }) {
    return this.request('/exams', { method: 'POST', body: JSON.stringify(data) });
  }
  static async listExams() {
    return this.request('/exams');
  }
  static async myExamAttempts() {
    return this.request('/exams/me/attempts');
  }
  static async startExam(examId: number) {
    return this.request(`/exams/${examId}/start`, { method: 'POST' });
  }
  static async submitExam(attemptId: number, answers: Record<string, string | string[]>) {
    return this.request(`/exams/attempts/${attemptId}/submit`, { method: 'POST', body: JSON.stringify({ answers }) });
  }
  static async logProctorEvent(attemptId: number, event_type: string, detail?: string, media_url?: string) {
    return this.request(`/exams/attempts/${attemptId}/proctor-event`, {
      method: 'POST',
      body: JSON.stringify({ event_type, detail, media_url }),
    });
  }
  static async examAttemptsForReview(examId: number) {
    return this.request(`/exams/${examId}/attempts`);
  }

  // ─── Gradebook + item analysis ──────────────────────────────────────────────
  static async gradebook(bankId: number) {
    return this.request(`/gradebook/bank/${bankId}`);
  }
  static async itemAnalysis(bankId: number) {
    return this.request(`/gradebook/bank/${bankId}/item-analysis`);
  }
  static async downloadGradebookCsv(bankId: number): Promise<string> {
    const res = await fetch(`${getBaseUrl()}/gradebook/bank/${bankId}/export.csv`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    return res.text();
  }

  static async getKTKeys(companyId?: string, activeOnly: boolean = true) {
    const params = new URLSearchParams({ active_only: String(activeOnly) });
    if (companyId) params.append('company_id', companyId);
    return this.request(`/kt/keys?${params.toString()}`);
  }

  static async revokeKTKey(keyId: string) {
    return this.request(`/kt/keys/${keyId}`, { method: 'DELETE' });
  }

  // ─── Chat (AI Assistant) ──────────────────────────────────────────────────

  // FIXED: was /kt/ask — correct endpoint is /kt/chat/message (alias /kt/ask also exists)
  static async askKTQuestion(sessionId: string, message: string, rawKey?: string) {
    const headers = this.getHeaders();
    if (rawKey) headers['X-KT-Key'] = rawKey;
    return this.request('/kt/chat/message', {
      method: 'POST',
      headers,
      body: JSON.stringify({ session_id: sessionId, message }),
    });
  }

  static async getSessionMessages(sessionId: string, page: number = 1) {
    return this.request(`/kt/chat/sessions/${sessionId}/messages?page=${page}&size=50`);
  }

  /** ChatGPT-style multi-session history for the current user (optionally per company). */
  static async getKTSessions(companyId?: string) {
    const q = companyId ? `?company_id=${encodeURIComponent(companyId)}` : '';
    return this.request(`/kt/chat/sessions${q}`);
  }

  static async renameKTSession(sessionId: string, title: string) {
    return this.request(`/kt/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  }

  static async deleteKTSession(sessionId: string) {
    return this.request(`/kt/chat/sessions/${sessionId}`, { method: 'DELETE' });
  }

  /** Redeem an access key → persistent access to a company's project knowledge. */
  static async redeemKTKey(rawKey: string) {
    return this.request('/kt/keys/redeem', {
      method: 'POST',
      body: JSON.stringify({ raw_key: rawKey }),
    });
  }

  /** Companies/projects the current user can access (via grants). */
  static async getMyKTAccess() {
    return this.request('/kt/me/access');
  }

  /** Knowledge documents the current user has authored. */
  static async getMyKTDocuments() {
    return this.request('/kt/me/documents');
  }

  static async submitChatFeedback(messageId: string, feedback: 1 | -1, note?: string) {
    return this.request('/kt/chat/feedback', {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, feedback, note }),
    });
  }

  // ─── Knowledge Graph ──────────────────────────────────────────────────────

  static async getKTGraphData(projectIds: string[], companyId?: string, rawKey?: string) {
    const params = new URLSearchParams();
    projectIds.forEach(id => params.append('project_ids', id));
    if (companyId) params.append('company_id', companyId);
    const headers = this.getHeaders();
    if (rawKey) headers['X-KT-Key'] = rawKey;
    return this.request(`/kt/explorer/graph?${params.toString()}`, { headers });
  }

  static async getKTGraphNeighborhoodData(nodeId: string, rawKey?: string) {
    const headers = this.getHeaders();
    if (rawKey) headers['X-KT-Key'] = rawKey;
    return this.request(`/kt/explorer/graph/${nodeId}/neighborhood`, { headers });
  }

  static async getKTTimeline(projectIds: string | string[], companyId?: string, rawKey?: string) {
    const ids = Array.isArray(projectIds) ? projectIds : [projectIds];
    const params = new URLSearchParams();
    ids.forEach(id => params.append('project_ids', id));
    if (companyId) params.append('company_id', companyId);
    const headers = this.getHeaders();
    if (rawKey) headers['X-KT-Key'] = rawKey;
    return this.request(`/kt/explorer/timeline?${params.toString()}`, { headers });
  }

  static async getKTGraphStats(companyId?: string) {
    const params = companyId ? `?company_id=${companyId}` : '';
    return this.request(`/kt/explorer/stats${params}`);
  }

  // ─── Insights & Analytics ─────────────────────────────────────────────────

  // FIXED: was getKTAnalytics() — correct name and endpoint
  static async getKTAnalyticsSummary() {
    return this.request('/kt/insights/summary');
  }

  // Deprecated alias — kept for backwards compat, routes to summary
  static async getKTAnalytics(projectId?: string) {
    if (projectId) return this.request(`/kt/insights/project/${projectId}`);
    return this.request('/kt/insights/summary');
  }

  static async getKTCompanyAnalytics(companyId?: string) {
    const params = companyId ? `?company_id=${companyId}` : '';
    return this.request(`/kt/insights/company${params}`);
  }

  static async getKTProjectAnalytics(projectId: string) {
    return this.request(`/kt/insights/project/${projectId}`);
  }

  static async getKTGroupInsights() {
    return this.request('/kt/insights/group');
  }

  static async getMyDocTraction() {
    return this.request('/kt/insights/my-docs');
  }

  // FIXED: was /kt/suggestions — correct endpoint is /kt/insights/gaps
  static async getKTDiscoverySuggestions(companyId?: string, page: number = 1) {
    const params = new URLSearchParams({ page: String(page), size: '20' });
    if (companyId) params.append('company_id', companyId);
    return this.request(`/kt/insights/gaps?${params.toString()}`);
  }

  // Backwards-compat alias (used in KnowledgeDiscovery.tsx)
  static async getKTGaps(resolved = false) {
    return this.request(`/kt/insights/gaps?resolved=${resolved}`);
  }

  static async resolveKTGap(gapId: string, docId?: string) {
    const params = docId ? `?doc_id=${docId}` : '';
    return this.request(`/kt/insights/gaps/${gapId}/resolve${params}`, { method: 'PATCH' });
  }

  // ─── Handoff Engine ───────────────────────────────────────────────────────

  // FIXED: was getKTHandoffGaps(userId) — now requires both departing_user_id AND company_id
  static async analyze_handoff_pre(departingUserId: number, companyId: string) {
    return this.request(
      `/kt/handoffs/analyze?departing_user_id=${departingUserId}&company_id=${companyId}`
    );
  }

  static async listKTHandoffs() {
    return this.request('/kt/handoffs');
  }

  static async getKTHandoff(handoffId: string) {
    return this.request(`/kt/handoffs/${handoffId}`);
  }

  static async initiateKTHandoff(data: {
    departing_user_id: number;
    company_id: string;
    receiving_user_id?: number;
    mentor_id?: number;
    departure_date?: string;
    notes?: string;
    handoff_type?: string;
  }) {
    return this.request('/kt/handoffs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateHandoffChecklist(handoffId: string, itemIndex: number, done: boolean) {
    return this.request(
      `/kt/handoffs/${handoffId}/checklist?item_index=${itemIndex}&done=${done}`,
      { method: 'PATCH' }
    );
  }

  // ─── Notifications ────────────────────────────────────────────────────────

  static async getKTNotifications(unreadOnly: boolean = false, page: number = 1) {
    return this.request(`/kt/notifications?unread_only=${unreadOnly}&page=${page}`);
  }

  static async markKTNotificationRead(notifId: string) {
    return this.request(`/kt/notifications/${notifId}/read`, { method: 'PATCH' });
  }

  static async markAllKTNotificationsRead() {
    return this.request('/kt/notifications/read-all', { method: 'PATCH' });
  }

  // ─── Mentor Inbox ─────────────────────────────────────────────────────────

  static async getMentorInbox(page = 1, size = 20) {
    return this.request(`/kt/mentor/inbox?page=${page}&size=${size}`);
  }

  // ─── Co-Author Search ─────────────────────────────────────────────────────

  static async searchCoAuthors(query: string, groupId?: number) {
    const params = new URLSearchParams({ q: query });
    if (groupId) params.append('group_id', groupId.toString());
    return this.request(`/kt/coauthor-search?${params.toString()}`);
  }

  // ─── Onboarding ───────────────────────────────────────────────────────────

  static async generateOnboardingBundle(data: {
    project_id: string;
    company_id: string;
    new_user_id?: number;
    ttl_days?: number;
  }) {
    return this.request('/kt/onboarding/bundle', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ─── Draft Saving ─────────────────────────────────────────────────────────

  static async saveQuizDraft(payload: any) {
    return this.request('/quiz/draft', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  static async loadQuizDraft() {
    return this.request('/quiz/draft');
  }

  static async saveKTDraft(payload: any) {
    return this.request('/kt/draft', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  static async loadKTDraft() {
    return this.request('/kt/draft');
  }

  // --- MISSING ENDPOINTS ADDED DURING AUDIT REMEDIATION ---

  static async getTargetLevels(): Promise<Array<{ id: string, name: string }>> {
    try {
      const response = await this.request('/admin/target-levels');
      if (Array.isArray(response)) return response;
      throw new Error('Invalid response');
    } catch (e) {
      // Fallback for registry data to simulate a dynamically fetched array from the API.
      return [
        { id: 'group', name: 'Group (Specific)' },
        { id: 'batch', name: 'Batch (All Groups in Batch)' },
        { id: 'vertical', name: 'Vertical (All Batches)' },
        { id: 'dept', name: 'Department (All Verticals)' },
        { id: 'org', name: 'Organization (Global)' }
      ];
    }
  }

  static async getDocTypes(): Promise<Array<{ id: string, name: string }>> {
    try {
      return await this.request('/kt/registry/doc-types');
    } catch {
      return [
        { id: 'architecture_decision', name: 'Architecture Decision (ADR)' },
        { id: 'runbook', name: 'Operations Runbook' },
        { id: 'design_doc', name: 'System Design Doc' },
        { id: 'onboarding_guide', name: 'Onboarding Guide' },
        { id: 'post_mortem', name: 'Post-Mortem Analysis' }
      ];
    }
  }

  static async getComplexities(): Promise<Array<{ id: string, name: string }>> {
    try {
      return await this.request('/kt/registry/complexities');
    } catch {
      return [
        { id: 'beginner', name: 'Beginner' },
        { id: 'intermediate', name: 'Intermediate' },
        { id: 'advanced', name: 'Advanced' },
        { id: 'expert', name: 'Expert' }
      ];
    }
  }

  static async getAccessLevels(): Promise<Array<{ id: string, name: string }>> {
    try {
      return await this.request('/kt/registry/access-levels');
    } catch {
      return [
        { id: 'project_only', name: 'Project Only' },
        { id: 'company_wide', name: 'Company Wide' },
        { id: 'public', name: 'Public' }
      ];
    }
  }

  static async getSensitivities(): Promise<Array<{ id: string, name: string }>> {
    try {
      return await this.request('/kt/registry/sensitivities');
    } catch {
      return [
        { id: 'low', name: 'Low' },
        { id: 'medium', name: 'Medium' },
        { id: 'high', name: 'High' },
        { id: 'confidential', name: 'Confidential' }
      ];
    }
  }

  static async contactSupport(payload: any) {
    return this.request('/contact', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  static async getProgrammingLanguages() {
    return this.request('/code/languages');
  }


  static async getAllTaskStatus() {
    return this.request('/admin/tasks/status');
  }

  /** Cohort health for a GROUP. Backend: GET /reports/group/{group_id}/cohort-health */
  static async getCohortHealth(groupId: string | number) {
    return this.request(`/reports/group/${groupId}/cohort-health`);
  }

  static async exportDeep(payload: any) {
    return this.request(`/export/banks/${payload.batch_id}/deep`, {
      method: 'GET'
    });
  }

  static getNotificationStream() {
    return this.getEventSource('/auth/notifications/stream');
  }

  // NOTE: getKTSprints()/getKTSprintInsights() were removed. They called
  // /kt/projects/{id}/sprints and /kt/sprints/{id}/insights, neither of which
  // exists on the backend, and nothing in the app called them. Re-add them
  // alongside the endpoints if sprint insights are built.
}
