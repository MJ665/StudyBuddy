// Browser-side Sentry init (Next.js 15 loads this before hydration).
// No-op when NEXT_PUBLIC_SENTRY_DSN is unset, so dev is unaffected.
import * as Sentry from '@sentry/nextjs';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

Sentry.init({
  dsn,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || 'production',
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.2),
  // Session Replay: sample a slice of sessions, but always capture on error.
  replaysSessionSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_REPLAY_SAMPLE_RATE ?? 0.1),
  replaysOnErrorSampleRate: 1.0,
  // Sentry structured logs (JS Logs).
  enableLogs: true,
  sendDefaultPii: false,
  integrations: [Sentry.replayIntegration()],
});

if (dsn) Sentry.setTag('component', 'web');

// Instruments App Router client-side navigations for tracing.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
