'use client';
// ============================================================
// React Query Client Setup
// ============================================================
// Global singleton QueryClient with sensible defaults for the
// StudyBuddy application. Import this from layout or providers.

import { QueryClient } from '@tanstack/react-query';

let queryClientInstance: QueryClient | null = null;

export function getQueryClient(): QueryClient {
  if (typeof window === 'undefined') {
    // Server: always create a new instance
    return new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30 * 1000,       // 30 seconds
          retry: false,               // Don't retry on server
        },
      },
    });
  }

  // Browser: re-use singleton
  if (!queryClientInstance) {
    queryClientInstance = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,       // 1 minute
          gcTime: 10 * 60 * 1000,     // 10 minutes
          retry: 1,
          refetchOnWindowFocus: false,
        },
        mutations: {
          retry: 0,
        },
      },
    });
  }
  return queryClientInstance;
}
