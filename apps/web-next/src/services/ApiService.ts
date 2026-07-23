// In production, set NEXT_PUBLIC_API_BASE=https://your-backend-url.railway.app in Vercel env vars
// In local dev, this falls back to /api which is proxied to localhost:8000 via next.config.ts rewrites
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || (process.env.NODE_ENV === 'development' ? '/api' : '/api');
// Force relative path for proxying if not explicitly an absolute URL in env
const getBaseUrl = () => {
  if (typeof window === 'undefined') return API_BASE;
  if (API_BASE.startsWith('http')) return API_BASE;
  return API_BASE;
};

export interface AIResponseEnvelope<T = any> {
  ai_generated: boolean;
  data: T;
  model: string;
  metadata: {
    cached: boolean;
    duration_ms: number;
    prompt_id: string;
  };
  fallback_used: boolean;
  error?: string;
}

export interface SystemConfig {
  supported_languages: Array<{ id: string; name: string; monaco_language: string }>;
  difficulty_levels: string[];
  resource_categories: string[];
  ai_languages: string[];
  learner_levels: string[];
  password_patterns: string[];
  notification_types: Array<{ id: string; icon: string; color: string; bg: string }>;
}

export interface UserMe {
  id: number;
  email: string;
  full_name: string;
  role: string;
  group_id: number;
  profile_photo_url?: string;
  custom_slug?: string;
  success?: boolean;
}


export interface ConsistencyResult {
  user_id?: number;
  attempt_count?: number;
  mean_accuracy?: number;
  std_dev?: number;
  cv: number | null;
  interpretation: string;
}

export interface EngagementDecayResult {
  decay_curve?: Array<{ period: string; engagement: number }>;
  [key: string]: unknown;
}

export interface CompositeHealthResult {
  composite_index?: number;
  components?: Record<string, number>;
  [key: string]: unknown;
}

export interface BatchInsights {
  insights: any[];
  fullMetrics?: any;
}

export interface AiInsightsResult {
  insights?: any[];
  summary?: string | null;
}

export interface ExecutiveSummary {
  summary: string | null;
}

class ApiService {
  private static configCache: SystemConfig | null = null;
  public static getHeaders(contentType: string = 'application/json') {
    const headers: Record<string, string> = {};
    if (contentType) {
      headers['Content-Type'] = contentType;
    }
    const token = localStorage.getItem('study_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  static async request(endpoint: string, options: RequestInit = {}, isRetry = false, retryCount = 0): Promise<any> {
    if (!options.headers) {
      options.headers = this.getHeaders();
    }
    try {
      const response = await fetch(`${getBaseUrl()}${endpoint}`, {
        ...options,
        credentials: 'include'
      });

      if (response.ok) {
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          return response.json();
        }
        if (contentType.includes("text/html")) {
          throw new Error("API returned HTML instead of JSON. Check backend status.");
        }
        return response.blob();
      }

      if (response.status === 401 && !isRetry) {
        try {
          const refreshRes = await fetch(`${getBaseUrl()}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
          });

          if (refreshRes.ok) {
            const data = await refreshRes.json();
            if (data.access_token) {
              localStorage.setItem('study_token', data.access_token);
              options.headers = {
                ...options.headers,
                ...this.getHeaders(),
              };
              return this.request(endpoint, options, true);
            }
          }
        } catch (err) {
          console.error("Critical Protocol Failure: Silent rotation aborted.", err);
        }

        this.logout();
        throw new Error("Session expired. Strategic synchronization lost.");
      }

      let errMessage = `Error ${response.status}`;
      try {
        const bodyText = await response.text();
        try {
          const errData = JSON.parse(bodyText);
          errMessage = typeof errData.detail === 'object' ? JSON.stringify(errData.detail) : (errData.detail || errData.error || errMessage);
        } catch {
          errMessage = bodyText || errMessage;
        }
      } catch { }
      throw new Error(errMessage);
    } catch (err: any) {
      // Retry on network errors (ECONNREFUSED) up to 3 times
      if (retryCount < 3 && (err.name === 'TypeError' || err.message.includes('fetch'))) {
        await new Promise(resolve => setTimeout(resolve, 1500 * (retryCount + 1)));
        return this.request(endpoint, options, isRetry, retryCount + 1);
      }
      throw err;
    }
  }

  static logout() {
    const hadToken = !!localStorage.getItem('study_token');
    localStorage.removeItem('study_token');
    localStorage.removeItem('study_user');

    // Attempt to clear the HttpOnly refresh cookie silently
    fetch(`${getBaseUrl()}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => { });

    const publicPaths = ['/profile/', '/p/', '/reset-password'];
    const isPublicPath = publicPaths.some(p => window.location.pathname.startsWith(p));

    if (!isPublicPath) {
      setTimeout(() => {
        if (window.location.pathname === '/') {
          if (hadToken) window.location.reload();
        } else {
          window.location.href = '/';
        }
      }, 100);
    }
  }

  static async getSystemConfig(): Promise<SystemConfig> {
    if (this.configCache) return this.configCache;
    this.configCache = await this.request('/system/config');
    return this.configCache!;
  }

  static async getPromotableRoles(): Promise<string[]> {
    return this.request('/auth/roles/promotable');
  }

  // ─── Auth ─────────────────────────────────────────────────────────────────
  static async getGroups() {
    return this.request('/auth/groups');
  }

  static async login(groupId: number, fullName: string, password: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ group_id: groupId, full_name: fullName, password })
    });
  }

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

  static async superAdminLogin(password: string) {
    return this.request('/auth/superadmin/login', {
      method: 'POST',
      body: JSON.stringify({ password })
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

  static async bulkAddUsers(groupId: number, users: any[], passwordPattern?: string) {
    return this.request(`/auth/groups/${groupId}/users/bulk`, {
      method: 'POST',
      body: JSON.stringify({ users, password_pattern: passwordPattern })
    });
  }

  static async forgotPassword(email: string, groupId: number) {
    return this.request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email, group_id: groupId })
    });
  }

  static async resetPassword(email: string, groupId: number, otpCode: string, newPassword: string) {
    return this.request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, group_id: groupId, otp_code: otpCode, new_password: newPassword })
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

  static async createGroupV3(data: { batch_id: number; name: string; password_pattern?: string }) {
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

  static async getGroupHealth(groupId: number) {
    return this.request(`/reports/group/${groupId}/health`);
  }

  static async getBatchReport(batchId: number) {
    return this.request(`/reports/batch/${batchId}/summary`);
  }

  static async getMemberGrowthAtlas(userId: number) {
    return this.request(`/reports/member/${userId}/growth-atlas`);
  }

  static async getUserIntel(userId: number, refresh: boolean = false): Promise<AIResponseEnvelope> {
    return this.request(`/intel/user/${userId}/insights${refresh ? '?refresh=true' : ''}`);
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

  static async markAllRead() {
    return this.request('/interaction/notifications/read-all', { method: 'POST' });
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

  static async getKTCompanies() {
    return this.request('/kt/companies');
  }

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
  }) {
    return this.request('/exams', { method: 'POST', body: JSON.stringify(data) });
  }
  static async listExams() {
    return this.request('/exams');
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

  static getEventSource(endpoint: string, rawKey?: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('study_token') : null;
    let url = `${getBaseUrl()}${endpoint}`;

    // Add token as query param for EventSource since headers aren't supported in browser native EventSource
    if (token) {
      url += (url.includes('?') ? '&' : '?') + `token=${token}`;
    }
    if (rawKey) {
      url += (url.includes('?') ? '&' : '?') + `key=${rawKey}`;
    }

    return new EventSource(url);
  }
  static getNotificationStream() {
    return this.getEventSource('/auth/notifications/stream');
  }

  // NOTE: getKTSprints()/getKTSprintInsights() were removed. They called
  // /kt/projects/{id}/sprints and /kt/sprints/{id}/insights, neither of which
  // exists on the backend, and nothing in the app called them. Re-add them
  // alongside the endpoints if sprint insights are built.
}
export default ApiService;
