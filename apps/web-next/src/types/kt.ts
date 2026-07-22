// ============================================================
// KT Module — Centralised Type Definitions
// ============================================================
// Mirrors the Pydantic schemas in kt_schemas.py exactly.
// All optional fields match nullable=True columns in kt_model.py.

export type KTRole = 'Member' | 'Mentor' | 'GroupAdmin' | 'LDAdmin' | 'Owner';

// ─── Company ─────────────────────────────────────────────────────────────────

export interface KTCompany {
  id: string;
  name: string;
  domain?: string;
  is_active: boolean;
  created_at: string;
}

// ─── Project ──────────────────────────────────────────────────────────────────

export interface KTProjectMember {
  user_id: number;
  full_name?: string;
  role_in_project: string;
}

export interface KTProject {
  id: string;
  name: string;
  description?: string;
  company_id: string;
  client_name?: string;
  tech_stack: string[];
  status: string;
  doc_count: number;
  ingested_doc_count: number;
  knowledge_coverage_score: number;
  created_at: string;
  members: KTProjectMember[];
}

// ─── Document ─────────────────────────────────────────────────────────────────

export type DocStatus =
  | 'draft'
  | 'submitted'
  | 'under_review'
  | 'approved'
  | 'rejected'
  | 'ingested'
  | 'deprecated';

export type DocType =
  | 'architecture_decision'
  | 'meeting_notes'
  | 'post_mortem'
  | 'runbook'
  | 'design_doc'
  | 'onboarding_guide'
  | 'tech_spike'
  | 'retrospective'
  | 'bug_analysis'
  | 'api_documentation'
  | 'deployment_guide'
  | 'security_review'
  | 'performance_analysis'
  | 'knowledge_base';

export type IngestionStatus =
  | 'pending'
  | 'chunking'
  | 'embedding'
  | 'graph_building'
  | 'complete'
  | 'failed';

export interface KTDocument {
  id: string;
  project_id: string;
  company_id: string;
  author_id?: number;
  mentor_id?: number;
  title: string;
  doc_type: DocType;
  knowledge_domain?: string;
  tech_stack: string[];
  tags: string[];
  complexity: string;
  is_evergreen: boolean;
  access_level: string;
  sensitivity: string;
  co_author_ids: number[];
  co_author_names: string[];
  co_author_emails: string[];
  client_name?: string;
  date_range_start?: string;
  date_range_end?: string;
  sprint?: string;
  milestone?: string;
  problem_statement?: string;
  decisions_made: Record<string, unknown>[];
  outcome?: string;
  conclusion?: string;
  open_questions: string[];
  lessons_learned: string[];
  body_markdown: string;
  summary_ai?: string;
  auto_tags: string[];
  status: DocStatus;
  version: number;
  quality_score?: number;
  header_completeness?: number;
  word_count: number;
  read_time_minutes: number;
  ingestion_status?: IngestionStatus;
  endorsement_count: number;
  created_at: string;
  updated_at?: string;
  submitted_at?: string;
  approved_at?: string;
  ingested_at?: string;
  can_edit: boolean;
}

export interface KTDocumentVersion {
  id: string;
  document_id: string;
  version: number;
  body_markdown: string;
  changed_by_id?: number;
  change_summary?: string;
  created_at: string;
}

export interface KTAttachment {
  id: string;
  document_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  download_url?: string;
  created_at: string;
}

// ─── Access Keys ──────────────────────────────────────────────────────────────

export interface KTAccessKey {
  id: string;
  key_prefix: string;
  scope_label?: string;
  company_id: string;
  project_ids: string[];
  recipient_email?: string;
  expires_at?: string;
  use_count: number;
  max_uses?: number;
  is_onboarding_key: boolean;
  revoked_at?: string;
  last_used_at?: string;
  created_at: string;
}

export interface KTKeyWithRaw extends KTAccessKey {
  raw_key: string; // Returned ONCE at generation time only
}

export interface KTKeyVerification {
  valid: boolean;
  company_id?: string;
  project_ids?: string[];
  scope_label?: string;
  expires_at?: string;
  error?: string;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface KTSourceMetadata {
  doc_id: string;
  doc_title: string;
  doc_type: string;
  project_name: string;
  date_range?: string;
  excerpt: string;
  relevance_score: number;
}

export interface KTChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: KTSourceMetadata[];
  confidence_score?: number;
  was_answered?: boolean;
  latency_ms?: number;
  created_at: string;
}

export interface KTChatSession {
  id: string;
  company_id: string;
  project_ids: string[];
  message_count: number;
  started_at: string;
}

// ─── Handoff ─────────────────────────────────────────────────────────────────

export type HandoffType =
  | 'senior_to_junior'
  | 'departure'
  | 'cross_team'
  | 'project_reassignment';

export type HandoffStatus = 'initiated' | 'in_progress' | 'completed' | 'cancelled';

export interface HandoffChecklistItem {
  item: string;
  done: boolean;
  required: boolean;
  completed_at?: string;
}

export interface KTHandoff {
  id: string;
  company_id: string;
  organization_id: number;
  departing_user_id?: number;
  receiving_user_id?: number;
  mentor_id?: number;
  departure_date?: string;
  status: HandoffStatus;
  handoff_type: HandoffType;
  checklist: HandoffChecklistItem[];
  knowledge_transfer_score?: number;
  gap_analysis: {
    documented_count: number;
    covered_doc_types: string[];
    missing_doc_types: string[];
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  };
  notes?: string;
  initiated_at: string;
  completed_at?: string;
  hr_approved_at?: string;
}

export interface HandoffGapAnalysis {
  gaps: string[];
  attrition_risk: 'LOW' | 'MEDIUM' | 'HIGH';
  documented_count: number;
}

// ─── Notifications ────────────────────────────────────────────────────────────

export interface KTNotification {
  id: string;
  type: string;
  title: string;
  body?: string;
  resource_type?: string;
  resource_id?: string;
  is_read: boolean;
  created_at: string;
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export interface KTProjectInsights {
  project_id: string;
  project_name: string;
  company_id: string;
  total_docs: number;
  approved_docs: number;
  ingested_docs: number;
  pending_docs: number;
  quality_avg?: number;
  contributor_count: number;
  top_queried_topics: Record<string, unknown>[];
  unanswered_count: number;
  last_activity_at?: string;
}

export interface KTCompanyInsights {
  health_score: number;
  score_trend: number;
  coverage_score: number;
  freshness_score: number;
  depth_score: number;
  engagement_score: number;
  contribution_score: number;
  handoff_score: number;
  total_docs: number;
  ingested_docs: number;
  total_projects: number;
  covered_projects: number;
  total_queries: number;
  unanswered_queries: number;
  active_contributors: number;
  at_risk_users: number;
  stale_docs: number;
  top_contributors: Record<string, unknown>[];
  knowledge_gaps: Record<string, unknown>[];
  domain_coverage: Record<string, number>;
}

// ─── Knowledge Graph ─────────────────────────────────────────────────────────

export interface KTGraphNode {
  id: string;
  label: string;
  type: 'document' | 'concept' | 'project' | 'person';
  doc_type?: DocType;
  status?: DocStatus;
  size?: number;
}

export interface KTGraphLink {
  source: string;
  target: string;
  relation: string;
  weight?: number;
}

export interface KTGraphData {
  nodes: KTGraphNode[];
  links: KTGraphLink[];
}

// ─── Knowledge Gaps ───────────────────────────────────────────────────────────

export interface KTGap {
  id: string;
  query_text: string;
  occurrence_count: number;
  first_asked_at: string;
  last_asked_at: string;
  resolved: boolean;
  priority: number;
}

// ─── Sprint Tracking ─────────────────────────────────────────────────────────

export interface KTSprint {
  id: string;
  project_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: 'active' | 'completed' | 'planned';
  created_at: string;
}

export interface KTSprintInsights {
  sprint_id: string;
  total_documents: number;
  approved_documents: number;
  unresolved_queries: number;
  code_coverage_percentage?: number;
  velocity_trend?: number;
}
