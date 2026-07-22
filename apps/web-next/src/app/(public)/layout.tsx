'use client';

import React from 'react';
import { ToastProvider } from '@/components/ui/Toast';

/** Public (anonymous) pages: login, password recovery, public profiles. */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}
