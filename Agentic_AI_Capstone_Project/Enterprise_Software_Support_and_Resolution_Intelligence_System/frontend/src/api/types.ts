// Mirrors backend/app/schemas/*.py and db/models.py enums field-for-field.
// Keep in sync by hand — there is no shared schema generation in this
// project, so a backend field rename must be mirrored here manually.

export type UserRole = "support_agent" | "admin";

export type Category = "usage" | "integration" | "billing" | "incident" | "security" | "out_of_scope";
export type Severity = "Low" | "Medium" | "High" | "Critical";
export type RetrievalMode = "RAG" | "SQL" | "Hybrid" | "Critical";
export type ConfidenceTier = "High" | "Medium" | "Low";
export type ConversationStatus = "open" | "in_progress" | "resolved" | "escalated" | "closed" | "archived";
export type IngestionJobStatus = "pending" | "processing" | "completed" | "failed";
export type SourceType = "chunk" | "table" | "diagram" | "sql";

// ---------------------------------------------------------------------------
// Auth — schemas/auth.py
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  // No role field, deliberately — mirrors the backend's RegisterRequest:
  // self-registration always creates a support_agent account.
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  role: UserRole;
  expires_in: number;
}

export interface LogoutResponse {
  status: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface PasswordResetRequestRequest {
  email: string;
}

export interface PasswordResetRequestResponse {
  message: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

export interface PasswordResetConfirmResponse {
  status: string;
}

// ---------------------------------------------------------------------------
// Chat — schemas/chat.py, agent_contracts.py
// ---------------------------------------------------------------------------

export interface ChatRequest {
  query: string;
  customer_id: number;
  conversation_id?: string | null;
}

export interface SourceRef {
  type: SourceType;
  source_document: string | null;
  section_header: string | null;
  page_number: number | null;
  table: string | null;
  record_id: number | null;
}

export interface ChatResponse {
  answer: string;
  category: Category | null;
  severity: Severity | null;
  retrieval_mode: RetrievalMode | null;
  confidence_score: number | null;
  confidence_tier: ConfidenceTier | null;
  sources: SourceRef[];
  escalated: boolean;
  flagged_for_review: boolean;
  trace_id: string;
  conversation_id: string;
  retrieval_retry_count: number;
  reflection_loopback_count: number;
}

// SSE frame payloads — routes_chat.py's _chat_event_stream. `node` events
// only ever carry whichever of these fields that node's own delta touched.
export interface ChatStreamNodeEvent {
  node: string;
  category?: Category;
  retrieval_mode?: RetrievalMode;
  severity_initial?: Severity;
  severity_final?: Severity;
  confidence_score?: number;
  confidence_tier?: ConfidenceTier;
  escalation_flag?: boolean;
  retrieval_retry_count?: number;
  reflection_loopback_count?: number;
}

export interface ChatStreamErrorEvent {
  message: string;
}

export type ChatStreamEvent =
  | { event: "node"; data: ChatStreamNodeEvent }
  | { event: "done"; data: ChatResponse }
  | { event: "error"; data: ChatStreamErrorEvent };

// ---------------------------------------------------------------------------
// Conversations — routes_conversations.py (inline models)
// ---------------------------------------------------------------------------

export interface ConversationSummary {
  conversation_id: string;
  customer_id: number;
  last_message_at: string;
  status: ConversationStatus;
  escalated: boolean;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

export interface MessageOut {
  role: string;
  content: string;
  created_at: string;
  confidence_tier: ConfidenceTier | null;
  sources: SourceRef[] | null;
  trace_id: string | null;
  category: Category | null;
  severity: Severity | null;
  retrieval_mode: RetrievalMode | null;
  confidence_score: number | null;
  flagged_for_review: boolean;
  escalated: boolean;
}

export interface ConversationDetailResponse {
  conversation_id: string;
  messages: MessageOut[];
}

// ---------------------------------------------------------------------------
// Ingest — schemas/ingest.py
// ---------------------------------------------------------------------------

export interface IngestResponse {
  job_id: string;
  status: string;
}

export interface IngestStats {
  assets_new: number;
  assets_unchanged_skipped: number;
  assets_updated: number;
  assets_retired: number;
}

export interface IngestStatusResponse {
  job_id: string;
  document_id: string;
  status: IngestionJobStatus;
  stats: IngestStats | null;
}

export interface IngestDeleteResponse {
  document_id: string;
  assets_retired: number;
}

// ---------------------------------------------------------------------------
// Customers — routes_customers.py (frontend integration pass, inline model)
// ---------------------------------------------------------------------------

export interface CustomerSummary {
  customer_id: number;
  company_name: string;
  subscription_tier: string | null;
  account_status: string | null;
  region: string | null;
}

export interface CustomerListResponse {
  customers: CustomerSummary[];
  total: number;
}

// ---------------------------------------------------------------------------
// Documents — routes_documents.py (A5, inline model)
// ---------------------------------------------------------------------------

export interface DocumentSummary {
  document_id: string;
  doc_title: string | null;
  product_version: string | null;
  category: string | null;
  ingested_at: string;
  content_hash: string;
  active_asset_count: number;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
}

// ---------------------------------------------------------------------------
// Users — schemas/users.py (admin-only management, lower-priority page)
// ---------------------------------------------------------------------------

export interface UserResponse {
  user_id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
}

export interface UserCreateRequest {
  email: string;
  password: string;
  role: UserRole;
}

export interface UserUpdateRequest {
  email?: string | null;
  role?: UserRole | null;
}

// ---------------------------------------------------------------------------
// Metrics — routes_metrics.py (inline model)
// ---------------------------------------------------------------------------

export interface MetricsResponse {
  window: { from: string; to: string };
  latency_ms: { p50: number | null; p95: number | null };
  cost_per_ticket_usd: number | null;
  escalation_rate: number | null;
  last_eval_run_at: string | null;
  task_success_rate: number | null;
  sql_correctness: number | null;
  query_routing_accuracy: number | null;
  risk_classification_accuracy: number | null;
  escalation_recall: number | null;
  faithfulness: number | null;
  answer_relevance: number | null;
  context_precision: number | null;
  context_recall: number | null;
}

// ---------------------------------------------------------------------------
// Health — routes_health.py
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: "ok" | "degraded";
  postgres: string;
  redis: string;
  azure_openai: string;
}
