import { API_BASE, getBaseUrl, AIResponseEnvelope, SystemConfig, UserMe, ConsistencyResult, EngagementDecayResult, CompositeHealthResult, BatchInsights, AiInsightsResult, ExecutiveSummary } from './apiShared';

/* eslint-disable @typescript-eslint/no-explicit-any */
export class ApiClient0 {
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

      // Auth endpoints (login/register/forgot/reset/refresh) legitimately return
      // 401/4xx for bad input — do NOT run the silent token-refresh dance or the
      // "session expired" message there; let the real API error surface.
      const isAuthEndpoint = /\/auth\/(login|register|forgot-password|reset-password|refresh|superadmin\/login)/.test(endpoint);

      if (response.status === 401 && !isRetry && !isAuthEndpoint) {
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

    // Public pages a guest can legitimately sit on — a 401 here is expected
    // (e.g. the login page's initial "am I logged in?" probe) and must NOT
    // trigger a redirect. Note "/" is now the marketing landing (public).
    const path = window.location.pathname;
    const publicPrefixes = [
      '/login', '/forgot-password', '/reset-password',
      '/privacy', '/terms', '/contact-me', '/onboard',
      '/profile/', '/p/',
    ];
    const isPublicPath = path === '/' || publicPrefixes.some((p) => path.startsWith(p));

    // On an authenticated page whose session just expired, send the user to the
    // sign-in page (NOT the marketing home). hadToken avoids a redirect when we
    // were never logged in to begin with.
    if (!isPublicPath && hadToken) {
      setTimeout(() => { window.location.href = '/login'; }, 100);
    }
  }

  static async getSystemConfig(): Promise<SystemConfig> {
    if (this.configCache) return this.configCache;
    this.configCache = await this.request('/system/config');
    return this.configCache!;
  }

  static async getUserIntel(userId: number, refresh: boolean = false): Promise<AIResponseEnvelope> {
    return this.request(`/intel/user/${userId}/insights${refresh ? '?refresh=true' : ''}`);
  }

  static async markAllRead() {
    return this.request('/interaction/notifications/read-all', { method: 'POST' });
  }

  static async getKTCompanies() {
    return this.request('/kt/companies');
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
}
