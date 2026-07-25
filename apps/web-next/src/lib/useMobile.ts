'use client';

import { useEffect, useState } from 'react';

/**
 * Returns true when the viewport is at or below `breakpoint` px (default 768,
 * Tailwind's `md`). SSR-safe: starts false, resolves on mount, and stays in
 * sync via a matchMedia listener. Use to drive drawer/collapse behavior.
 */
export function useMobile(breakpoint: number = 768): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const update = () => setIsMobile(mq.matches);
    update();
    // addEventListener('change') is the modern API; Safari <14 used addListener.
    if (mq.addEventListener) {
      mq.addEventListener('change', update);
      return () => mq.removeEventListener('change', update);
    }
    mq.addListener(update);
    return () => mq.removeListener(update);
  }, [breakpoint]);

  return isMobile;
}

export default useMobile;
