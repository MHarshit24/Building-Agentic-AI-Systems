import type {
  ConversationDetailResponse,
  ConversationSummary,
  CustomerSummary,
  DocumentSummary,
  MetricsResponse,
  UserResponse,
} from "../api/types";

export const MOCK_CUSTOMERS: CustomerSummary[] = [
  { customer_id: 1042, company_name: "Acme Corp", subscription_tier: "Growth", account_status: "active", region: "us-east" },
  { customer_id: 2201, company_name: "Beta LLC", subscription_tier: "Standard", account_status: "active", region: "eu-west" },
  { customer_id: 887, company_name: "Gamma Industries", subscription_tier: "Standard", account_status: "active", region: "us-west" },
  { customer_id: 4310, company_name: "Delta Systems", subscription_tier: "Enterprise", account_status: "active", region: "apac" },
  { customer_id: 512, company_name: "Epsilon Retail", subscription_tier: "Standard", account_status: "active", region: "us-east" },
];

export const MOCK_USERS_BY_EMAIL: Record<string, { password: string; user: UserResponse }> = {
  "agent1@enterprise-support.local": {
    password: "DevPassword123!",
    user: {
      user_id: 3,
      email: "agent1@enterprise-support.local",
      role: "support_agent",
      is_active: true,
      created_at: "2026-01-05T09:00:00Z",
      last_login_at: "2026-08-01T14:22:00Z",
    },
  },
  "admin1@enterprise-support.local": {
    password: "DevPassword123!",
    user: {
      user_id: 1,
      email: "admin1@enterprise-support.local",
      role: "admin",
      is_active: true,
      created_at: "2026-01-05T09:00:00Z",
      last_login_at: "2026-08-02T08:10:00Z",
    },
  },
};

export const MOCK_CONVERSATIONS: ConversationSummary[] = [
  {
    conversation_id: "conv_9f1a2b3c",
    customer_id: 1042,
    last_message_at: "2026-08-02T16:44:00Z",
    status: "open",
    escalated: false,
  },
  {
    conversation_id: "conv_7e6d5c4b",
    customer_id: 2201,
    last_message_at: "2026-08-02T11:12:00Z",
    status: "escalated",
    escalated: true,
  },
  {
    conversation_id: "conv_1122aabb",
    customer_id: 887,
    last_message_at: "2026-07-30T09:05:00Z",
    status: "resolved",
    escalated: false,
  },
  {
    conversation_id: "conv_deadbeef",
    customer_id: 4310,
    last_message_at: "2026-07-22T13:40:00Z",
    status: "archived",
    escalated: false,
  },
];

export const MOCK_CONVERSATION_DETAILS: Record<string, ConversationDetailResponse> = {
  conv_9f1a2b3c: {
    conversation_id: "conv_9f1a2b3c",
    messages: [
      {
        role: "user",
        content: "How do I reset a customer's API key after a suspected leak?",
        created_at: "2026-08-02T16:43:10Z",
        confidence_tier: null,
        sources: null,
        trace_id: "lf_trace_a1",
        category: null,
        severity: null,
        retrieval_mode: null,
        confidence_score: null,
        flagged_for_review: false,
        escalated: false,
      },
      {
        role: "assistant",
        content:
          "Go to Account Settings → API Keys → Revoke, then issue a new key from the same panel. The old key is invalidated immediately and any in-flight requests using it will start returning 401s within a few seconds.",
        created_at: "2026-08-02T16:44:00Z",
        confidence_tier: "High",
        sources: [
          {
            type: "chunk",
            source_document: "API Integration & Authentication Guide",
            section_header: "Rotating API Keys",
            page_number: 4,
            table: null,
            record_id: null,
          },
        ],
        trace_id: "lf_trace_a1",
        category: "usage",
        severity: "Low",
        retrieval_mode: "RAG",
        confidence_score: 0.93,
        flagged_for_review: false,
        escalated: false,
      },
    ],
  },
  conv_7e6d5c4b: {
    conversation_id: "conv_7e6d5c4b",
    messages: [
      {
        role: "user",
        content: "Our production API has been returning 500s for the last 10 minutes across all regions.",
        created_at: "2026-08-02T11:10:00Z",
        confidence_tier: null,
        sources: null,
        trace_id: "lf_trace_b7",
        category: null,
        severity: null,
        retrieval_mode: null,
        confidence_score: null,
        flagged_for_review: false,
        escalated: false,
      },
      {
        role: "assistant",
        content:
          "This matches an active Critical incident (INC-4471) already logged for the affected region. I've escalated this to the on-call engineering team with full context — you'll be contacted directly.",
        created_at: "2026-08-02T11:12:00Z",
        confidence_tier: "High",
        sources: [
          { type: "sql", source_document: null, section_header: null, page_number: null, table: "incident_logs", record_id: 4471 },
        ],
        trace_id: "lf_trace_b7",
        category: "incident",
        severity: "Critical",
        retrieval_mode: "Critical",
        confidence_score: 0.97,
        flagged_for_review: false,
        escalated: true,
      },
    ],
  },
  conv_1122aabb: {
    conversation_id: "conv_1122aabb",
    messages: [
      {
        role: "user",
        content: "What's our SLA response time for a High severity ticket?",
        created_at: "2026-07-30T09:04:20Z",
        confidence_tier: null,
        sources: null,
        trace_id: "lf_trace_c3",
        category: null,
        severity: null,
        retrieval_mode: null,
        confidence_score: null,
        flagged_for_review: false,
        escalated: false,
      },
      {
        role: "assistant",
        content: "High severity tickets have a 4-hour first-response SLA and a 24-hour resolution target under the Standard plan.",
        created_at: "2026-07-30T09:05:00Z",
        confidence_tier: "High",
        sources: [
          { type: "table", source_document: "SLA & Support Operation Policy", section_header: "Response Time Commitments", page_number: 2, table: null, record_id: null },
        ],
        trace_id: "lf_trace_c3",
        category: "usage",
        severity: "Low",
        retrieval_mode: "RAG",
        confidence_score: 0.89,
        flagged_for_review: false,
        escalated: false,
      },
    ],
  },
  conv_deadbeef: {
    conversation_id: "conv_deadbeef",
    messages: [
      {
        role: "user",
        content: "Why was my invoice higher this month?",
        created_at: "2026-07-22T13:39:00Z",
        confidence_tier: null,
        sources: null,
        trace_id: "lf_trace_d9",
        category: null,
        severity: null,
        retrieval_mode: null,
        confidence_score: null,
        flagged_for_review: false,
        escalated: false,
      },
      {
        role: "assistant",
        content: "Your account moved from the Standard to the Growth tier on the 15th, which is prorated into this invoice.",
        created_at: "2026-07-22T13:40:00Z",
        confidence_tier: "Medium",
        sources: [{ type: "sql", source_document: null, section_header: null, page_number: null, table: "support_tickets", record_id: 8802 }],
        trace_id: "lf_trace_d9",
        category: "billing",
        severity: "Low",
        retrieval_mode: "SQL",
        confidence_score: 0.76,
        flagged_for_review: true,
        escalated: false,
      },
    ],
  },
};

export const MOCK_DOCUMENTS: DocumentSummary[] = [
  {
    document_id: "api_error_codes_troubleshooting_handbook",
    doc_title: "API Error Codes Troubleshooting Handbook",
    product_version: "v3",
    category: "integration",
    ingested_at: "2026-07-10T10:00:00Z",
    content_hash: "8f3a...c21",
    active_asset_count: 42,
  },
  {
    document_id: "api_integration_authentication_guide",
    doc_title: "API Integration & Authentication Guide",
    product_version: "v3",
    category: "integration",
    ingested_at: "2026-07-10T10:02:00Z",
    content_hash: "1b7e...a90",
    active_asset_count: 38,
  },
  {
    document_id: "sla_support_operation_policy",
    doc_title: "SLA & Support Operation Policy",
    product_version: null,
    category: "usage",
    ingested_at: "2026-07-11T08:30:00Z",
    content_hash: "cc02...44f",
    active_asset_count: 19,
  },
  {
    document_id: "security_vulnerability_response_policy",
    doc_title: "Security Vulnerability Response Policy",
    product_version: null,
    category: "security",
    ingested_at: "2026-07-12T15:45:00Z",
    content_hash: "77aa...901",
    active_asset_count: 27,
  },
];

export const MOCK_METRICS: MetricsResponse = {
  window: { from: "2026-07-26T00:00:00Z", to: "2026-08-02T00:00:00Z" },
  latency_ms: { p50: 1180, p95: 2340 },
  cost_per_ticket_usd: 0.028,
  escalation_rate: 0.12,
  last_eval_run_at: "2026-08-02T02:00:00Z",
  task_success_rate: 0.93,
  sql_correctness: 0.97,
  query_routing_accuracy: 0.96,
  risk_classification_accuracy: 0.95,
  escalation_recall: 1.0,
  faithfulness: 0.88,
  answer_relevance: 0.85,
  context_precision: 0.79,
  context_recall: 0.81,
};

// A function, not a static snapshot — MOCK_USERS_BY_EMAIL gains entries at
// runtime when the mock /auth/register handler "creates" an account, and
// callers (the /users and /auth/refresh handlers) need to see those too.
export function getMockAllUsers(): UserResponse[] {
  return Object.values(MOCK_USERS_BY_EMAIL).map((u) => u.user);
}
