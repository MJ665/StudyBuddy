'use client';
// ============================================================
// ReactQueryProvider — Client Component
// ============================================================
// Wraps the app with TanStack Query's QueryClientProvider.
// Import this in the root layout.tsx as a client-boundary wrapper.

import { QueryClientProvider } from '@tanstack/react-query';
import { getQueryClient } from '@/lib/queryClient';
import { type ReactNode } from 'react';

export function ReactQueryProvider({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
