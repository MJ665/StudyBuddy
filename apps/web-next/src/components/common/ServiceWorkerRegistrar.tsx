'use client';

import { useEffect } from 'react';

/**
 * Registers the PWA service worker (public/sw.js) on the client. Mounted once in
 * the root layout. Registration is best-effort and never blocks the app.
 */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
    // Only register on secure origins (https or localhost).
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') return;
    const onLoad = () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        /* registration failures are non-fatal */
      });
    };
    window.addEventListener('load', onLoad);
    return () => window.removeEventListener('load', onLoad);
  }, []);

  return null;
}
