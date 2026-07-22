// ============================================================
// KT RBAC Permission Matrix
// ============================================================
// Maps user roles to KT module capabilities.
// Always use these helpers instead of role comparisons in JSX.

import type { KTRole } from '@/types/kt';

// ─── Role tier ordering (higher = more permissions) ──────────────────────────
const ROLE_TIER: Record<KTRole, number> = {
  Member: 0,
  Mentor: 1,
  GroupAdmin: 2,
  LDAdmin: 3,
  Owner: 4,
};

function atLeast(role: KTRole, minimum: KTRole): boolean {
  return ROLE_TIER[role] >= ROLE_TIER[minimum];
}

// ─── KT Permissions ──────────────────────────────────────────────────────────

export const ktPermissions = {
  // ─── Document Actions ────────────────────────────────────────────────────
  canCreateDocument: (role: KTRole) => atLeast(role, 'Member'),
  canEditDocument: (role: KTRole, isAuthorOrCoAuthor: boolean) =>
    isAuthorOrCoAuthor || atLeast(role, 'Mentor'),
  canSubmitDocument: (role: KTRole, isAuthor: boolean) =>
    isAuthor || atLeast(role, 'Mentor'),
  canReviewDocument: (role: KTRole) => atLeast(role, 'Mentor'),
  canApproveDocument: (role: KTRole) => atLeast(role, 'Mentor'),
  canTriggerIngestion: (role: KTRole) => atLeast(role, 'Mentor'),
  canDeprecateDocument: (role: KTRole) => atLeast(role, 'Mentor'),
  canDeleteDocument: (role: KTRole) => atLeast(role, 'GroupAdmin'),
  canEndorseDocument: (role: KTRole) => atLeast(role, 'Member'),

  // ─── Project Actions ──────────────────────────────────────────────────────
  canCreateProject: (role: KTRole) => atLeast(role, 'Mentor'),
  canEditProject: (role: KTRole) => atLeast(role, 'Mentor'),
  canAddProjectMembers: (role: KTRole) => atLeast(role, 'Mentor'),

  // ─── Company Actions ──────────────────────────────────────────────────────
  canCreateCompany: (role: KTRole) => atLeast(role, 'GroupAdmin'),
  canViewCompanyAnalytics: (role: KTRole) => atLeast(role, 'Mentor'),

  // ─── Access Key Actions ───────────────────────────────────────────────────
  canGenerateKey: (role: KTRole) => atLeast(role, 'Mentor'),
  canRevokeKey: (role: KTRole) => atLeast(role, 'Mentor'),
  canViewKeys: (role: KTRole) => atLeast(role, 'Mentor'),

  // ─── Handoff Actions ──────────────────────────────────────────────────────
  canInitiateHandoff: (role: KTRole) => atLeast(role, 'Mentor'),
  canViewHandoffs: (role: KTRole) => atLeast(role, 'Mentor'),
  canGenerateOnboardingBundle: (role: KTRole) => atLeast(role, 'Mentor'),

  // ─── Analytics ────────────────────────────────────────────────────────────
  canViewAnalytics: (role: KTRole) => atLeast(role, 'Member'),
  canViewGroupInsights: (role: KTRole) => atLeast(role, 'Mentor'),

  // ─── KT Module Access ─────────────────────────────────────────────────────
  canAccessKTModule: (role: KTRole) => atLeast(role, 'Member'),
  canAccessMentorInbox: (role: KTRole) => atLeast(role, 'Mentor'),
  canAccessAdminControls: (role: KTRole) => atLeast(role, 'GroupAdmin'),
};

// ─── Role display helpers ─────────────────────────────────────────────────────

export function isMentorPlus(role: string, userGroupId?: number, contextGroupId?: number): boolean {
  if (!atLeast(role as KTRole, 'Mentor')) return false;
  // If a context group is provided, and the user is not an LDAdmin/Owner, they must belong to the group
  if (contextGroupId !== undefined && userGroupId !== undefined && !atLeast(role as KTRole, 'LDAdmin')) {
    return userGroupId === contextGroupId;
  }
  return true;
}

export function isGroupAdminPlus(role: string, userGroupId?: number, contextGroupId?: number): boolean {
  if (!atLeast(role as KTRole, 'GroupAdmin')) return false;
  if (contextGroupId !== undefined && userGroupId !== undefined && !atLeast(role as KTRole, 'LDAdmin')) {
    return userGroupId === contextGroupId;
  }
  return true;
}

export function isLDAdminPlus(role: string): boolean {
  return atLeast(role as KTRole, 'LDAdmin');
}
