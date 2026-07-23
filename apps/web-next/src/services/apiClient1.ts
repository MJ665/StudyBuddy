import { API_BASE, getBaseUrl, AIResponseEnvelope, SystemConfig, UserMe, ConsistencyResult, EngagementDecayResult, CompositeHealthResult, BatchInsights, AiInsightsResult, ExecutiveSummary } from './apiShared';
import { ApiClient0 } from './apiClient0';

/* eslint-disable @typescript-eslint/no-explicit-any */
export class ApiClient1 extends ApiClient0 {
  static async getPromotableRoles(): Promise<string[]> {
    return this.request('/auth/roles/promotable');
  }

  // ─── Auth ─────────────────────────────────────────────────────────────────
  static async getGroups() {
    return this.request('/auth/groups');
  }

  // (legacy group-pattern login removed — Phase 6; use loginWithEmail)

  /** Email-first login (Phase 4 rebuild) — individual credentials.
   * Auth transport: short-lived access token in localStorage → Authorization
   * header (bootstrapped/renewed via the HttpOnly refresh cookie). Persisting
   * it here avoids the 401→refresh bounce on the first authed request. */
  static async loginWithEmail(email: string, password: string) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    if (res?.access_token) {
      localStorage.setItem('study_token', res.access_token);
    }
    return res;
  }

  static async getMe(): Promise<UserMe> {
    return this.request('/auth/me');
  }

  static async getOwnProfile(): Promise<UserMe & Record<string, unknown>> {
    return this.request('/auth/profile');
  }

  static async updateProfile(data: any) {
    return this.request('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }

  static async getUsers(params: { q?: string, role?: string, group_id?: number, page?: number, size?: number } = {}) {
    const q = new URLSearchParams();
    if (params.q) q.set('q', params.q);
    if (params.role) q.set('role', params.role);
    if (params.group_id) q.set('group_id', String(params.group_id));
    if (params.page) q.set('page', String(params.page));
    if (params.size) q.set('size', String(params.size));
    return this.request(`/auth/users/discovery?${q}`);
  }

  static async getUsersByGroup(groupId: number, page: number = 1, size: number = 50) {
    return this.request(`/auth/groups/${groupId}/users?page=${page}&size=${size}`);
  }

  static async createUser(data: { email: string, full_name: string, group_id: number, role: string }) {
    return this.request('/auth/users', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  /** Assign a SCOPED role. Backend: POST /intel/user/{id}/roles */
  static async assignUserRole(
    userId: number,
    role: string,
    scopeType: string = 'group',
    scopeId?: number
  ) {
    return this.request(`/intel/user/${userId}/roles`, {
      method: 'POST',
      body: JSON.stringify({ role, scope_type: scopeType, scope_id: scopeId ?? null })
    });
  }

  /** Update a user's primary role (e.g. Member → Mentor). Calls PATCH /auth/users/{id}/role */
  static async updateUserRole(userId: number, role: string) {
    return this.request(`/auth/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role })
    });
  }

  /** Remove a SCOPED role by its row id. Backend: DELETE /intel/user/{id}/roles/{roleId} */
  static async removeUserRole(userId: number, roleId: number) {
    return this.request(`/intel/user/${userId}/roles/${roleId}`, {
      method: 'DELETE'
    });
  }

  static async impersonateGroup(groupId: number) {
    return this.request(`/auth/groups/${groupId}/impersonate`, { method: 'POST' });
  }

  static async bulkAddUsers(groupId: number, users: any[]) {
    return this.request(`/auth/groups/${groupId}/users/bulk`, {
      method: 'POST',
      body: JSON.stringify({ users })
    });
  }

  static async forgotPassword(email: string) {
    return this.request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  static async resetPassword(email: string, otpCode: string, newPassword: string) {
    return this.request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, otp_code: otpCode, new_password: newPassword })
    });
  }

  static async adminResetPassword(userId: number, newPassword: string) {
    return this.request(`/admin/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword })
    });
  }

  static async changePassword(currentPassword: string, newPassword: string) {
    return this.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
  }

  static async logoutAll() {
    return this.request('/auth/logout-all', { method: 'POST' });
  }

  static async getSessions() {
    return this.request('/auth/me/sessions');
  }

  static async deleteUser(userId: number) {
    return this.request(`/auth/users/${userId}`, { method: 'DELETE' });
  }


  static async revokeSession(sessionId: number) {
    return this.request(`/auth/me/sessions/${sessionId}`, { method: 'DELETE' });
  }

  // ─── Quiz / Courses ───────────────────────────────────────────────────────
  static async getCourses(groupId: number) {
    return this.request(`/quiz/courses?group_id=${groupId}`);
  }

  static async createCourse(courseData: { name: string; group_id?: number }) {
    return this.request('/quiz/courses', {
      method: 'POST',
      body: JSON.stringify(courseData)
    });
  }

  static async getBanks(courseId?: number, page: number = 1, size: number = 50) {
    const q = new URLSearchParams();
    if (courseId) q.set('course_id', String(courseId));
    q.set('page', String(page));
    q.set('size', String(size));
    return this.request(`/quiz/banks?${q}`);
  }

  static async getBankById(bankId: number) {
    return this.request(`/quiz/banks/${bankId}`);
  }

  static async getBankQuestions(bankId: number, maxQs?: number) {
    const query = maxQs ? `?max=${maxQs}` : '';
    return this.request(`/quiz/banks/${bankId}/questions${query}`);
  }

  static async updateQuestion(questionId: number, updates: any) {
    return this.request(`/quiz/questions/${questionId}`, {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }

  static async deleteQuestion(questionId: number) {
    return this.request(`/quiz/questions/${questionId}`, { method: 'DELETE' });
  }

  static async createQuestionBank(bankData: any) {
    return this.request('/quiz/banks', {
      method: 'POST',
      body: JSON.stringify(bankData)
    });
  }

  static async updateBankMetadata(bankId: number, updates: Record<string, any>) {
    return this.request(`/quiz/banks/${bankId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates)
    });
  }

  static async deleteBank(bankId: number) {
    return this.request(`/quiz/banks/${bankId}`, { method: 'DELETE' });
  }

  static async importBank(courseId: number, name: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const token = localStorage.getItem('study_token');
    const response = await fetch(`${API_BASE}/quiz/banks/import?course_id=${courseId}&name=${encodeURIComponent(name)}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Import failed');
    }
    return response.json();
  }

  static async cloneBank(bankId: number) {
    return this.request(`/quiz/banks/${bankId}/clone`, { method: 'POST' });
  }

  static async publishBank(bankId: number, isPublic: boolean = true) {
    return this.request(`/quiz/banks/${bankId}/publish`, {
      method: 'PATCH',
      body: JSON.stringify({ is_public: isPublic })
    });
  }

  static async getTopics() {
    return this.request('/quiz/topics');
  }

  static async submitAttempt(payload: any) {
    return this.request('/quiz/attempts', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  static async getLeaderboard(bankId: number, search?: string) {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return this.request(`/quiz/banks/${bankId}/leaderboard${query}`);
  }

  static async markAttemptReviewed(attemptId: number, isReviewed: boolean) {
    return this.request(`/mentor/review`, {
      method: 'POST',
      body: JSON.stringify({ attempt_id: attemptId, is_reviewed: isReviewed })
    });
  }

  static async getMyStats() {
    return this.request('/quiz/my-stats');
  }

  static async getUserAssignmentHistory(userId: number) {
    return this.request(`/quiz/user/${userId}/assignments`);
  }

  static async getDailyChallenge() {
    return this.request('/quiz/challenges/daily');
  }

  static async subscribeVertical(verticalId: number, courseId: number) {
    return this.request(`/quiz/subscribe/vertical?vertical_id=${verticalId}&course_id=${courseId}`, { method: 'POST' });
  }

  static async subscribeGroup(groupId: number, courseId: number) {
    return this.request(`/quiz/subscribe/group?group_id=${groupId}&course_id=${courseId}`, { method: 'POST' });
  }

  // ─── Profile & Intelligence ──────────────────────────────────────────────
  static async getProfileBySlug(slug: string) {
    return this.request(`/intel/profile/${slug}`);
  }

  static async getOrgHierarchy() {
    return this.request('/intel/hierarchy/with-users');
  }

  // ─── Administration & Governance ──────────────────────────────────────────
  static async getSystemHealth() {
    return this.request('/admin/health');
  }

  static async triggerTask(taskName: string) {
    return this.request(`/admin/tasks/trigger/${taskName}`, { method: 'POST' });
  }

  static async seedDailyChallenges() {
    return this.request('/admin/seed-daily', { method: 'POST' });
  }

  static async notifyIntervention(data: { user_ids: number[], message: string }) {
    return this.request('/admin/notify-intervention', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async bulkAdminAction(userIds: number[], action: 'deactivate' | 'activate' | 'delete') {
    return this.request('/admin/bulk-action', {
      method: 'POST',
      body: JSON.stringify({ user_ids: userIds, action })
    });
  }

  // ─── Mentor Domain ───────────────────────────────────────────────────────────
  static async getMentorGroups() {
    return this.request('/mentor/groups');
  }

  static async getPendingReviews() {
    return this.request('/mentor/pending-reviews');
  }

  /** Unified mentor inbox: assessment reviews + KT docs awaiting approval.
   * (getMentorInbox already names the KT-sub-app queue at /kt/mentor/inbox.) */
  static async getUnifiedMentorInbox() {
    return this.request('/mentor/inbox');
  }

  static async getGroupStudents(groupId: number) {
    return this.request(`/mentor/group/${groupId}/students`);
  }

  static async getGroupAiSummary(groupId: number, force: boolean = false): Promise<AIResponseEnvelope> {
    return this.request(`/mentor/group/${groupId}/ai-summary${force ? '?force=true' : ''}`);
  }

  static async getStudentProfile(studentId: number) {
    return this.request(`/mentor/student/${studentId}/profile`);
  }

  static async getAIStudentInsight(studentId: number): Promise<AIResponseEnvelope> {
    return this.request(`/mentor/student/${studentId}/ai-insight`, { method: 'POST' });
  }

  static async getGroupStats(groupId: number) {
    return this.request(`/mentor/group/${groupId}/stats`);
  }

  static async getGroupActivityFeed(groupId: number) {
    return this.request(`/mentor/group/${groupId}/feed`);
  }

  static async reviewAttempt(data: {
    attempt_id: number;
    attempt_type: 'quiz' | 'coding';
    is_reviewed: boolean;
    mentor_comment?: string;
    override_score?: number;
  }) {
    return this.request('/mentor/review', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static async bulkReviewAttempts(data: {
    attempt_ids: number[];
    attempt_type: 'quiz' | 'coding';
    is_reviewed: boolean;
    bulk_comment?: string;
  }) {
    return this.request('/mentor/bulk-review', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // ─── Organization & Hierarchy ─────────────────────────────────────────
  static async getOrgTree() {
    return this.request('/org/tree');
  }

  static async getOrgs() {
    return this.request('/org/organizations');
  }

  static async createOrg(data: { name: string }) {
    const slug = data.name.toLowerCase().replace(/ /g, '-').replace(/[^\w-]/g, '');
    return this.request('/org/', {
      method: 'POST',
      body: JSON.stringify({ ...data, slug })
    });
  }

  static async getDepartments(orgId?: number) {
    const query = orgId ? `?organization_id=${orgId}` : '';
    return this.request(`/org/departments${query}`);
  }

  static async createDept(data: { name: string; org_id: number; description?: string }) {
    return this.request(`/org/${data.org_id}/departments`, {
      method: 'POST',
      body: JSON.stringify({ name: data.name, description: data.description || '' })
    });
  }

  static async getVerticals(deptId?: number) {
    const query = deptId ? `?department_id=${deptId}` : '';
    return this.request(`/org/verticals${query}`);
  }

  static async createVertical(data: { name: string; dept_id: number; description?: string }) {
    return this.request(`/org/departments/${data.dept_id}/verticals`, {
      method: 'POST',
      body: JSON.stringify({ name: data.name, description: data.description || '' })
    });
  }

  static async getBatches(vertId?: number) {
    const query = vertId ? `?vertical_id=${vertId}` : '';
    return this.request(`/org/batches${query}`);
  }

  static async createBatch(data: { name: string; vertical_id: number; description?: string }) {
    return this.request(`/org/verticals/${data.vertical_id}/batches`, {
      method: 'POST',
      body: JSON.stringify({ name: data.name, description: data.description || '' })
    });
  }

  static async createGroupV3(data: { batch_id: number; name: string }) {
    return this.request('/org/groups', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // Lifecycle updates
  static async updateOrg(id: number, data: any) {
    return this.request(`/org/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }
  static async deleteOrg(id: number) {
    return this.request(`/org/${id}`, { method: 'DELETE' });
  }
  static async updateDept(id: number, data: any) {
    return this.request(`/org/departments/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }
  static async deleteDept(id: number) {
    return this.request(`/org/departments/${id}`, { method: 'DELETE' });
  }
  static async updateVertical(id: number, data: any) {
    return this.request(`/org/verticals/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }
  static async deleteVertical(id: number) {
    return this.request(`/org/verticals/${id}`, { method: 'DELETE' });
  }
  static async updateBatch(id: number, data: any) {
    return this.request(`/org/batches/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }
  static async deleteBatch(id: number) {
    return this.request(`/org/batches/${id}`, { method: 'DELETE' });
  }
  static async updateGroup(id: number, data: any) {
    return this.request(`/org/groups/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  }
  static async deleteGroup(id: number) {
    return this.request(`/org/groups/${id}`, { method: 'DELETE' });
  }



  // ─── Reports & Analytics ──────────────────────────────────────────────────
  static async getComparativeAnalytics() {
    return this.request('/reports/analytics/comparative');
  }

  static async getLndStats() {
    return this.request('/reports/lnd/stats');
  }

}
