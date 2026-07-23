import { API_BASE, getBaseUrl, AIResponseEnvelope, SystemConfig, UserMe, ConsistencyResult, EngagementDecayResult, CompositeHealthResult, BatchInsights, AiInsightsResult, ExecutiveSummary } from './apiShared';
import { ApiClient1 } from './apiClient1';

/* eslint-disable @typescript-eslint/no-explicit-any */
export class ApiClient2 extends ApiClient1 {
  static async getGroupHealth(groupId: number) {
    return this.request(`/reports/group/${groupId}/health`);
  }

  static async getBatchReport(batchId: number) {
    return this.request(`/reports/batch/${batchId}/summary`);
  }

  static async getMemberGrowthAtlas(userId: number) {
    return this.request(`/reports/member/${userId}/growth-atlas`);
  }

  static async getUserInsights(userId: number, refresh: boolean = false) {
    return this.getUserIntel(userId, refresh);
  }

  static async getUserAISummary(userId: number, refresh: boolean = false): Promise<AIResponseEnvelope> {
    return this.request(`/intel/user/${userId}/ai-summary${refresh ? '?refresh=true' : ''}`);
  }

  static async getPerformanceDistribution(params: { batch_id?: number; group_id?: number } = {}) {
    const q = new URLSearchParams();
    if (params.batch_id) q.set('batch_id', String(params.batch_id));
    if (params.group_id) q.set('group_id', String(params.group_id));
    return this.request(`/reports/analytics/performance-distribution?${q}`);
  }

  static async getLearningVelocity(userId: number) {
    return this.request(`/reports/analytics/learning-velocity/${userId}`);
  }

  static async getUserConsistency(userId: number): Promise<ConsistencyResult> {
    return this.request(`/reports/analytics/consistency/${userId}`);
  }

  static async getEngagementDecay(batchId?: number): Promise<EngagementDecayResult> {
    const q = batchId ? `?batch_id=${batchId}` : '';
    return this.request(`/reports/analytics/engagement-decay${q}`);
  }

  static async getCompositeHealthIndex(batchId?: number): Promise<CompositeHealthResult> {
    const q = batchId ? `?batch_id=${batchId}` : '';
    return this.request(`/reports/analytics/composite-health-index${q}`);
  }

  static async getCodingLeaderboard(params: { group_id?: number; batch_id?: number; page?: number } = {}) {
    const q = new URLSearchParams();
    if (params.group_id) q.set('group_id', String(params.group_id));
    if (params.batch_id) q.set('batch_id', String(params.batch_id));
    if (params.page) q.set('page', String(params.page));
    return this.request(`/reports/coding-leaderboard?${q}`);
  }

  static async exportBatchXlsx(batchId: number): Promise<Blob> {
    return this.request(`/reports/batch/${batchId}/xlsx`);
  }

  static async exportBatchCsv(batchId: number): Promise<Blob> {
    return this.request(`/reports/batch/${batchId}/csv`);
  }

  // ─── Assignments ──────────────────────────────────────────────────────────
  static async getMyAssignments() {
    return this.request('/assignments/my');
  }

  static async createAssignment(data: any) {
    return this.request('/assignments/', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async getAssignments(params: { target_type?: string, target_id?: number, page?: number, size?: number } = {}) {
    const q = new URLSearchParams();
    if (params.target_type) q.set('target_type', params.target_type);
    if (params.target_id) q.set('target_id', String(params.target_id));
    if (params.page) q.set('page', String(params.page));
    if (params.size) q.set('size', String(params.size));
    return this.request(`/assignments/?${q}`);
  }

  static async updateAssignment(id: number, data: any) {
    return this.request(`/assignments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }

  static async deleteAssignment(id: number) {
    return this.request(`/assignments/${id}`, { method: 'DELETE' });
  }

  static async manuallyCompleteAssignment(assignmentId: number, userId: number) {
    return this.request(`/assignments/${assignmentId}/complete/${userId}`, {
      method: 'POST'
    });
  }

  // ─── SECTION 12: AI Executive Intelligence ────────────────────────────────
  static async getProfileAtlas(slug: string, refresh: boolean = false): Promise<AIResponseEnvelope> {
    return this.request(`/intel/profile/${slug}/atlas${refresh ? '?refresh=true' : ''}`);
  }

  static async getProfileRegistry(slug: string) {
    return this.request(`/intel/profile/${slug}/registry`);
  }

  static async getBatchIntel(batchId: number, refresh: boolean = false): Promise<BatchInsights> {
    return this.request(`/admin/batch/${batchId}/insights${refresh ? '?refresh=true' : ''}`);
  }

  static async getBatchAiInsights(batchId: number, refresh: boolean = false): Promise<AiInsightsResult> {
    return this.request(`/admin/batch/${batchId}/ai-insights${refresh ? '?refresh=true' : ''}`);
  }

  static async getBatchExecutiveSummary(batchId: number, refresh: boolean = false): Promise<ExecutiveSummary> {
    return this.request(`/admin/batch/${batchId}/executive-summary${refresh ? '?refresh=true' : ''}`);
  }

  static async getGlobalIntel(refresh: boolean = false): Promise<BatchInsights> {
    return this.request(`/admin/analytics/insights${refresh ? '?refresh=true' : ''}`);
  }

  static async getAnalyticsAiInsights(refresh: boolean = false): Promise<AiInsightsResult> {
    return this.request(`/admin/analytics/ai-insights${refresh ? '?refresh=true' : ''}`);
  }

  // ─── Coding Practice ───────────────────────────────────────────────────────
  static async getCodingQuestions(courseId?: number, page?: number) {
    const q = new URLSearchParams();
    if (courseId) q.set('course_id', String(courseId));
    if (page) q.set('page', String(page));
    return this.request(`/code/questions?${q}`);
  }

  static async getCodingQuestionById(id: number) {
    return this.request(`/code/questions/${id}`);
  }

  static async createCodingQuestion(data: any) {
    return this.request('/code/questions', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async updateCodingQuestion(id: number, updates: any) {
    return this.request(`/code/questions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates)
    });
  }

  static async deleteCodingQuestion(id: number) {
    return this.request(`/code/questions/${id}`, { method: 'DELETE' });
  }

  static async evaluateCode(questionId: number, code: string, language: string, timeSpent: number = 0): Promise<AIResponseEnvelope> {
    return this.request('/code/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        coding_question_id: questionId,
        submitted_code: code,
        language: language,
        time_spent_seconds: timeSpent
      })
    });
  }

  static async verifyCodingAttempt(attemptId: number) {
    return this.request(`/code/attempts/${attemptId}/verify`, { method: 'POST' });
  }

  static async getHint(questionId: number, hintLevel: number, userCode: string = "", language: string = "python"): Promise<AIResponseEnvelope> {
    return this.request('/code/hint', {
      method: 'POST',
      body: JSON.stringify({
        coding_question_id: questionId,
        hint_level: hintLevel,
        user_code: userCode,
        language: language
      })
    });
  }

  static async getMyCodingAttempts() {
    return this.request('/code/attempts/my');
  }

  // ─── Resources ────────────────────────────────────────────────────────────
  static async getPresignedUpload(
    groupId: number, userId: number, fileName: string, fileType: string,
    description: string = '', category: string = 'General'
  ) {
    return this.request('/resources/presigned-upload', {
      method: 'POST',
      body: JSON.stringify({ group_id: groupId, user_id: userId, file_name: fileName, file_type: fileType, description, category })
    });
  }

  static async getProfilePresignedUpload(fileName: string, fileType: string) {
    return this.request('/auth/presigned-upload-profile', {
      method: 'POST',
      body: JSON.stringify({ file_name: fileName, file_type: fileType })
    });
  }

  static async getGroupResources(groupId: number, page: number = 1, size: number = 50) {
    return this.request(`/resources/group/${groupId}?page=${page}&size=${size}`);
  }

  static async updateResourceMetadata(id: number, data: any) {
    return this.request(`/resources/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }

  static async deleteResource(resourceId: number) {
    return this.request(`/resources/${resourceId}`, { method: 'DELETE' });
  }

  static async getResourceComments(resourceId: number) {
    return this.request(`/resources/${resourceId}/comments`);
  }

  static async addResourceComment(resourceId: number, content: string) {
    return this.request(`/resources/${resourceId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content })
    });
  }

  // ─── Notifications ────────────────────────────────────────────────────────
  static async getNotifications() {
    return this.request('/interaction/notifications');
  }

  static async getUnreadCount() {
    return this.request('/interaction/notifications/unread-count');
  }

  static async markNotificationRead(notifId: number) {
    return this.request(`/interaction/notifications/${notifId}/read`, { method: 'PATCH' });
  }

  static async markAllNotificationsRead() {
    return this.markAllRead();
  }

  static async deleteNotification(notifId: number) {
    return this.request(`/interaction/notifications/${notifId}`, { method: 'DELETE' });
  }

  // ─── AI ───────────────────────────────────────────────────────────────────
  static async askAI(attemptId: number, questionId: number, userQuery: string) {
    return this.request('/ai/ask', {
      method: 'POST',
      body: JSON.stringify({ attempt_id: attemptId, question_id: questionId, user_query: userQuery })
    });
  }

  static async getAILearningPath(params: { goal: string, current_level?: string, available_hours_per_week?: number }) {
    return this.request('/ai/learning-path', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  static async getSavedLearningPaths() {
    return this.request('/ai/learning-paths');
  }

  static async getAINextTopic(groupId?: number) {
    return this.request('/ai/next-topic', {
      method: 'POST',
      body: JSON.stringify({ group_id: groupId })
    });
  }

  static async generateSmartQuiz(topic: string, difficulty: string = "Medium", numQuestions: number = 5, language: string = "English", questionType: string = "mcq_single") {
    return this.request('/ai/smart-quiz', {
      method: 'POST',
      body: JSON.stringify({ topic, difficulty, num_questions: numQuestions, language, question_type: questionType })
    });
  }

  static async explainQuestion(data: { question_text: string, correct_answer: string, user_answer?: string, context?: string }) {
    return this.request('/ai/explain', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async summarizeContent(content: string, summaryType: 'study_notes' | 'flashcards' | 'quiz_questions' = 'study_notes') {
    return this.request('/ai/summarize', {
      method: 'POST',
      body: JSON.stringify({ content, summary_type: summaryType })
    });
  }

  // ─── Interaction & Community ──────────────────────────────────────────────
  static async reportQuestion(questionId: number, data: { issue_type: string, description: string }) {
    return this.request(`/interaction/questions/${questionId}/report`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async getPendingReports() {
    return this.request('/interaction/reports/pending');
  }

  static async resolveReport(reportId: number) {
    return this.request(`/interaction/reports/${reportId}/resolve`, {
      method: 'PATCH'
    });
  }

  static async getDiscussions(questionId: number) {
    return this.request(`/interaction/questions/${questionId}/discussions`);
  }

  static async getGlobalDiscussions(bankId?: number, page: number = 1, size: number = 20) {
    const q = new URLSearchParams();
    if (bankId) q.set('bank_id', String(bankId));
    q.set('page', String(page));
    q.set('size', String(size));
    return this.request(`/interaction/discussions?${q}`);
  }

  static async addDiscussion(questionId: number, comment: string | { content: string, parent_id?: number }, parentId?: number) {
    const payload = typeof comment === 'string'
      ? { content: comment, parent_id: parentId }
      : comment;
    return this.request(`/interaction/questions/${questionId}/discussions`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // ─── Bookmarks ────────────────────────────────────────────────────────────
  static async toggleBookmark(questionId: number) {
    return this.request(`/interaction/questions/${questionId}/bookmark`, {
      method: 'POST'
    });
  }

  static async getBookmarkStatus(questionId: number) {
    return this.request(`/interaction/questions/${questionId}/bookmark-status`);
  }

  static async getBookmarks() {
    return this.request('/interaction/bookmarks');
  }

  // ─── Audit & Governance ───────────────────────────────────────────────────
  static async getAuditLogs(page: number = 1, size: number = 50, targetType?: string, actorId?: number) {
    const q = new URLSearchParams();
    q.set('page', String(page));
    q.set('size', String(size));
    if (targetType) q.set('target_type', targetType);
    if (actorId) q.set('actor_id', String(actorId));
    return this.request(`/admin/audit?${q}`);
  }

  static async getEmailLogs(page: number = 1, size: number = 50) {
    const q = new URLSearchParams();
    q.set('page', String(page));
    q.set('size', String(size));
    return this.request(`/admin/email-logs?${q}`);
  }

  static async getQuestionReports(resolved?: boolean) {
    const url = resolved !== undefined ? `/admin/reports?resolved=${resolved}` : '/admin/reports';
    return this.request(url);
  }

  static async resolveQuestionReport(reportId: number) {
    return this.request(`/admin/reports/${reportId}/resolve`, {
      method: 'PATCH'
    });
  }

  static async export_global_activity() {
    const token = localStorage.getItem('study_token');
    const response = await fetch(`${API_BASE}/admin/export-activity`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    if (!response.ok) throw new Error('Export failed. Authentication required.');
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `StudyBuddy_Global_Activity_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }

  static async getSecurityStats() {
    return this.request('/admin/security-stats');
  }

  static async getUserActivityHeatmap(userId: number) {
    return this.request(`/reports/analytics/heatmap/${userId}`);
  }

  static async getExecutiveReport(batchId: number) {
    return this.request(`/admin/reports/executive/${batchId}`);
  }

  static async getGroupLeaderboard(groupId: number) {
    return this.request(`/admin/groups/${groupId}/leaderboard`);
  }

  static async getQuizQuestions(bankId: number, maxQuestions?: number) {
    const query = maxQuestions ? `?max=${maxQuestions}` : '';
    return this.request(`/quiz/banks/${bankId}/questions${query}`);
  }
  static async syncInfrastructure() {
    return this.request('/admin/infrastructure/sync', { method: 'POST' });
  }
  // --- Public Profiles ---
  static async getPublicProfile(slug: string) {
    return this.request(`/intel/profile/${slug}`);
  }

  static async postProfileComment(slug: string, content: string) {
    return this.request(`/intel/profile/${slug}/comment`, {
      method: 'POST',
      body: JSON.stringify({ content })
    });
  }
  // ─── Knowledge Transfer (KT) ──────────────────────────────────────────────

  // ─── Companies ────────────────────────────────────────────────────────────

  static async listKTCompanies() {
    return this.getKTCompanies();
  }

  static async createKTCompany(data: { name: string; domain?: string }) {
    return this.request('/kt/companies', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ─── Projects ─────────────────────────────────────────────────────────────

  static async getKTProjects(companyId?: string) {
    const params = companyId ? `?company_id=${companyId}` : '';
    return this.request(`/kt/projects${params}`);
  }

  static async createKTProject(data: {
    name: string;
    company_id?: string;
    description?: string;
    client_name?: string;
    tech_stack?: string[];
    group_id?: number;
  }) {
    return this.request('/kt/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async getKTProjectDetails(projectId: string) {
    return this.request(`/kt/projects/${projectId}`);
  }

  static async updateKTProject(projectId: string, data: any) {
    return this.request(`/kt/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  static async addKTProjectMember(projectId: string, userId: number, role: string = 'member') {
    return this.request(`/kt/projects/${projectId}/members?user_id=${userId}&role_in_project=${role}`, {
      method: 'POST',
    });
  }

  // ─── Documents ────────────────────────────────────────────────────────────

  static async getKTDocuments(options: {
    project_id?: string;
    company_id?: string;
    status?: string;
    doc_type?: string;
    sprint?: string;
    search?: string;
    page?: number;
    size?: number;
  } | string = {}, accessKey?: string) {
    const headers = this.getHeaders();
    if (accessKey) headers['X-KT-Key'] = accessKey;

    // Backwards-compat: accept raw project_id string
    if (typeof options === 'string') {
      return this.request(`/kt/documents?project_id=${options}`, { headers });
    }
    const params = new URLSearchParams();
    Object.entries(options).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.append(k, String(v));
    });
    return this.request(`/kt/documents?${params.toString()}`, { headers });
  }

}
