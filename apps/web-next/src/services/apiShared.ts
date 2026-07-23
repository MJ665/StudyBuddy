// In production, set NEXT_PUBLIC_API_BASE=https://your-backend-url.railway.app in Vercel env vars
// In local dev, this falls back to /api which is proxied to localhost:8000 via next.config.ts rewrites
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || (process.env.NODE_ENV === 'development' ? '/api' : '/api');
// Force relative path for proxying if not explicitly an absolute URL in env
export const getBaseUrl = () => {
  if (typeof window === 'undefined') return API_BASE;
  if (API_BASE.startsWith('http')) return API_BASE;
  return API_BASE;
};

export interface AIResponseEnvelope<T = any> {
  ai_generated: boolean;
  data: T;
  model: string;
  metadata: {
    cached: boolean;
    duration_ms: number;
    prompt_id: string;
  };
  fallback_used: boolean;
  error?: string;
}

export interface SystemConfig {
  supported_languages: Array<{ id: string; name: string; monaco_language: string }>;
  difficulty_levels: string[];
  resource_categories: string[];
  ai_languages: string[];
  learner_levels: string[];
  notification_types: Array<{ id: string; icon: string; color: string; bg: string }>;
}

export interface UserMe {
  id: number;
  email: string;
  full_name: string;
  role: string;
  group_id: number;
  profile_photo_url?: string;
  custom_slug?: string;
  success?: boolean;
}


export interface ConsistencyResult {
  user_id?: number;
  attempt_count?: number;
  mean_accuracy?: number;
  std_dev?: number;
  cv: number | null;
  interpretation: string;
}

export interface EngagementDecayResult {
  decay_curve?: Array<{ period: string; engagement: number }>;
  [key: string]: unknown;
}

export interface CompositeHealthResult {
  composite_index?: number;
  components?: Record<string, number>;
  [key: string]: unknown;
}

export interface BatchInsights {
  insights: any[];
  fullMetrics?: any;
}

export interface AiInsightsResult {
  insights?: any[];
  summary?: string | null;
}

export interface ExecutiveSummary {
  summary: string | null;
}

