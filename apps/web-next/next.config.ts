import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

/**
 * The frontend talks to the backend through a SAME-ORIGIN reverse proxy:
 * the browser only ever calls `/api/*` on the frontend domain, and Next.js
 * rewrites that to the real FastAPI backend. This keeps the HttpOnly refresh
 * cookie first-party (SameSite=Lax just works — no CORS, no cross-site cookies).
 *
 * The backend origin is configurable via `API_PROXY_ORIGIN`:
 *   - local dev  → http://127.0.0.1:8000
 *   - production → https://studybuddy-api.mj665.in  (override in Vercel env)
 *
 * Because of this proxy, do NOT set NEXT_PUBLIC_API_BASE in Vercel — the client
 * must keep calling the same-origin `/api` (see src/services/apiShared.ts).
 */
const isDev = process.env.NODE_ENV === 'development';

const API_PROXY_ORIGIN = (
  process.env.API_PROXY_ORIGIN ||
  (isDev ? 'http://127.0.0.1:8000' : 'https://studybuddy-api.mj665.in')
).replace(/\/$/, '');

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_PROXY_ORIGIN}/api/:path*`,
      },
    ];
  },
};

// Wrap with Sentry: source-map upload (build-time, when SENTRY_AUTH_TOKEN is set),
// ad-blocker-resistant event tunnel, and the existing rewrite is preserved.
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  tunnelRoute: '/monitoring',
  disableLogger: true,
  // Only upload source maps when a build-time auth token is present.
  sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
  telemetry: false,
});

