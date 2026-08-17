// Mirrors app/schemas/domain.py and app/api/schemas/*.py on the backend.
// Keep these in sync by hand — there is no shared schema generation step.

export interface BudgetConstraint {
  currency: string;
  max_amount: number;
}

export interface TimelinePreference {
  preferred_date: string; // ISO date, e.g. "2027-05-20"
  duration_days: number;
}

// Keep in sync with app/llm/model_router.py::PROVIDERS.
export const PROVIDERS = ["azure", "anthropic", "gemini"] as const;
export type Provider = (typeof PROVIDERS)[number];

export const PROVIDER_LABELS: Record<Provider, string> = {
  azure: "Azure OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

export interface EventBrief {
  event_type: string;
  objective: string;
  audience_size: number;
  budget: BudgetConstraint;
  timeline: TimelinePreference;
  venue_preference?: string | null;
  constraints: string[];
  // None = default Azure -> Anthropic -> Gemini fallback chain (see
  // app/llm/model_router.py). Only meaningful on creation; a refine reuses
  // whichever provider the plan was originally created with.
  provider?: Provider | null;
  // None = app.config.Settings.quality_gate_threshold. Bounded 0.5-0.9 (see
  // app/api/schemas/requests.py). Only meaningful on creation; a refine
  // reuses whichever threshold the plan was originally created with.
  quality_gate_threshold?: number | null;
}

export interface LogisticsPlan {
  venue: string;
  capacity: number;
  layout_notes: string;
  catering: string;
  vendors: string[];
  equipment: string[];
}

export interface BudgetPlan {
  total_estimated_cost: number;
  currency: string;
  category_breakdown: Record<string, number>;
  within_budget: boolean;
}

export interface MarketingPlan {
  channels: string[];
  content_calendar: string[];
  outreach_start_date: string;
}

export interface ScheduleMilestone {
  name: string;
  date: string;
}

export interface ScheduleTimeline {
  milestones: ScheduleMilestone[];
  conflicts_detected: string[];
}

export interface Risk {
  name: string;
  likelihood: "low" | "medium" | "high";
  impact: "low" | "medium" | "high";
  mitigation: string;
}

export interface RiskRegister {
  risks: Risk[];
  contingency_notes: string;
}

export interface EventOverview {
  event_type: string;
  objective: string;
  audience_size: number;
  date: string;
  summary: string;
}

export interface EventBlueprint {
  overview: EventOverview;
  logistics: LogisticsPlan;
  budget: BudgetPlan;
  marketing: MarketingPlan;
  schedule: ScheduleTimeline;
  risks: RiskRegister;
}

export interface CritiqueNote {
  iteration: number;
  score: number;
  passed: boolean;
  revision_targets: string[];
  notes: Record<string, string>;
  // Computed once in ReflectionAgent.critique() and also reported to
  // Langfuse with these exact values — do not recompute these client-side,
  // or the UI risks showing numbers that drift from what Langfuse records.
  duration_ms: number | null;
  score_delta: number | null;
  threshold_delta: number | null;
}

export type PlanStatus = "in_progress" | "needs_review" | "completed" | "failed";

export const SPECIALIST_KEYS = ["logistics", "budget", "marketing", "schedule", "risk"] as const;
export type SpecialistKey = (typeof SPECIALIST_KEYS)[number];

export interface PlanResponse {
  plan_id: string;
  status: PlanStatus;
  iteration_count: number;
  max_iterations: number | null;
  // Minimum weighted critique score required to pass the quality gate
  // (see app/agents/reflection_agent.py) — gives "score 0.64" a bar to
  // compare against instead of a bare number.
  quality_gate_threshold: number;
  // Fixed at plan creation; carried through every refine on the same plan.
  provider: Provider | null;
  active_revision_targets: string[];
  specialist_outputs_ready: string[];
  blueprint: EventBlueprint | null;
  critique_history: CritiqueNote[];
  error_message: string | null;
}

export interface HealthResponse {
  status: string;
  llm_configured: boolean;
  // Providers with real credentials in the running backend, in display
  // order — the model picker only ever offers these.
  available_providers: Provider[];
  // The quality slider initializes to this value rather than hardcoding a
  // guess that could drift out of sync with the server's actual default.
  default_quality_gate_threshold: number;
}

// Bounds enforced server-side too (see app/api/schemas/requests.py) — kept
// here only so the slider's min/max/step match without a round trip.
export const QUALITY_GATE_THRESHOLD_MIN = 0.5;
export const QUALITY_GATE_THRESHOLD_MAX = 0.9;
export const QUALITY_GATE_THRESHOLD_STEP = 0.05;

export interface PlanSummary {
  plan_id: string;
  event_type: string;
  objective: string;
  status: PlanStatus;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  iteration_count: number;
  latest_score: number | null;
}

export interface ErrorDetail {
  code: string;
  message: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ErrorDetail | null;
  request_id: string;
}
