'use client';

/**
 * Typed React Query hooks (Phase 4) — the canonical data-access pattern.
 *
 * Server state belongs in React Query (caching, retries, invalidation);
 * client state in Zustand. New features add hooks here instead of calling
 * the legacy ApiService.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from './client';

export const queryKeys = {
  me: ['auth', 'me'] as const,
  banks: ['quiz', 'banks'] as const,
  bank: (id: number) => ['quiz', 'banks', id] as const,
  notifications: ['auth', 'notifications'] as const,
  unreadCount: ['auth', 'notifications', 'unread'] as const,
  assignments: (userId: number) => ['quiz', 'assignments', userId] as const,
};

export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async () => unwrap(await api.GET('/api/auth/me')),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useBanks() {
  return useQuery({
    queryKey: queryKeys.banks,
    queryFn: async () => unwrap(await api.GET('/api/quiz/banks')),
    staleTime: 60 * 1000,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications,
    queryFn: async () => unwrap(await api.GET('/api/auth/notifications')),
    staleTime: 30 * 1000,
  });
}

export function useUnreadNotificationCount() {
  return useQuery({
    queryKey: queryKeys.unreadCount,
    queryFn: async () =>
      unwrap(await api.GET('/api/auth/notifications/unread-count')),
    refetchInterval: 60 * 1000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (notificationId: number) =>
      unwrap(
        await api.PATCH('/api/auth/notifications/{notification_id}/read', {
          params: { path: { notification_id: notificationId } },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.notifications });
      void qc.invalidateQueries({ queryKey: queryKeys.unreadCount });
    },
  });
}
