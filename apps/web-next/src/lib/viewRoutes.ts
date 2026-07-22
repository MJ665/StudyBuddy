/**
 * Legacy view-name → real route mapping (Phase 4).
 *
 * The Sidebar/AppLayout still emit the old state-machine view names via
 * `onChangeView`; the route adapter in src/app/(app)/layout.tsx translates
 * them to URL navigation. When every component navigates with router.push
 * directly (Phase 6 cleanup), this file disappears.
 */

export const VIEW_TO_ROUTE: Record<string, string> = {
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  LD_ADMIN: '/admin',
  MENTOR: '/mentor',
  ADMIN: '/group-admin',
  QUIZ: '/assessment/run',
  QUIZ_RESULT: '/assessment/result',
  CODING_FLOW: '/coding/run',
  CODING_RESULT: '/coding/result',
  LEADERBOARD: '/leaderboard',
  PROFILE: '/profile',
  DISCUSSIONS: '/discussions',
  LIBRARY: '/library',
  ASSIGNMENTS: '/assignments',
  ATTEMPT_HISTORY: '/history',
  NOTIFICATIONS: '/notifications',
  RESOURCES: '/resources',
  USER_INTEL: '/intel',
  KNOWLEDGE_HUB: '/kt',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',
};

/** Route → view name, for highlighting the active sidebar item. */
export function viewForPath(pathname: string): string {
  if (pathname.startsWith('/kt')) return 'KNOWLEDGE_HUB';
  if (pathname.startsWith('/admin')) return 'LD_ADMIN';
  const entry = Object.entries(VIEW_TO_ROUTE).find(([, r]) => r === pathname);
  return entry ? entry[0] : 'DASHBOARD';
}
