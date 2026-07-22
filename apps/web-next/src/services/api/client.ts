'use client';

/**
 * Typed API client (Phase 4) — generated from the backend's OpenAPI schema.
 *
 *   import { api } from '@/services/api/client';
 *   const { data, error } = await api.GET('/api/quiz/banks');   // fully typed
 *
 * Types regenerate with:
 *   (apps/api) .venv/bin/python -c "import main, json; open('../web-next/openapi.json','w').write(json.dumps(main.app.openapi()))"
 *   (apps/web-next) npx openapi-typescript openapi.json -o src/services/api/schema.d.ts
 *
 * Auth semantics mirror the legacy ApiService: HTTP-only cookie session
 * (credentials: include), one transparent /auth/refresh retry on 401.
 * New code uses this + React Query hooks; the 258-method untyped ApiService
 * is frozen and shrinks as call-sites migrate (dies in Phase 6).
 */

import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './schema';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

// The OpenAPI paths already include the /api prefix; strip it from baseUrl
// when API_BASE is itself "/api" so we don't double it.
const baseUrl = API_BASE === '/api' ? '' : API_BASE.replace(/\/api$/, '');

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  refreshInFlight ??= fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      setTimeout(() => (refreshInFlight = null), 0);
    });
  return refreshInFlight;
}

const authMiddleware: Middleware = {
  async onResponse({ request, response }) {
    if (response.status !== 401) return response;
    // One transparent refresh + replay, shared across concurrent 401s.
    const refreshed = await tryRefresh();
    if (!refreshed) return response;
    return fetch(request.clone());
  },
};

export const api = createClient<paths>({
  baseUrl,
  credentials: 'include',
});
api.use(authMiddleware);

/** Throwing helper for React Query (`queryFn` should reject on error). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined) {
    const detail =
      typeof result.error === 'object' && result.error !== null && 'detail' in result.error
        ? String((result.error as { detail: unknown }).detail)
        : `Request failed (${result.response.status})`;
    throw new Error(detail);
  }
  return result.data as T;
}
