'use client';

// Root error boundary — catches errors thrown in the root layout itself, which
// the route-group error.tsx boundaries cannot. Must render <html>/<body>.
import { useEffect } from 'react';
import * as Sentry from '@sentry/nextjs';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, background: '#020617', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <div style={{ maxWidth: 420, textAlign: 'center' }}>
            <h2 style={{ fontSize: 24, fontWeight: 900, marginBottom: 8 }}>Something broke</h2>
            <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 24 }}>
              {error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={reset}
              style={{ padding: '12px 28px', background: '#4f46e5', color: '#fff', border: 0, borderRadius: 12, fontWeight: 700, cursor: 'pointer' }}
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
