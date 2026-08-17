// Deterministic, keyword-driven mock of POST /chat/stream's SSE frame
// sequence — drives the WorkflowDiagram through real node names/paths from
// the corrected graph topology (blueprint.md §11 replacement) without any
// real LLM/backend call. Query text picks the scenario; this mirrors the
// spirit of the reference HTML you shared (deterministic client-side
// simulation), not its styling.

import type { ChatRequest, ChatResponse, ConfidenceTier, RetrievalMode, Category, Severity, SourceRef, MessageOut } from "../api/types";
import { MOCK_CONVERSATIONS, MOCK_CONVERSATION_DETAILS } from "./fixtures";

export interface MockFrame {
  event: "node" | "done" | "error";
  data: object;
  delayMs: number;
}

function randomSuffix(): string {
  return Math.random().toString(16).slice(2, 10);
}

function sourcesFor(mode: RetrievalMode): SourceRef[] {
  if (mode === "SQL") {
    return [{ type: "sql", source_document: null, section_header: null, page_number: null, table: "support_tickets", record_id: 5521 }];
  }
  if (mode === "RAG") {
    return [
      {
        type: "chunk",
        source_document: "API Integration & Authentication Guide",
        section_header: "OAuth Token Refresh",
        page_number: 6,
        table: null,
        record_id: null,
      },
    ];
  }
  return [
    { type: "chunk", source_document: "API Error Codes Troubleshooting Handbook", section_header: "5xx Errors", page_number: 3, table: null, record_id: null },
    { type: "sql", source_document: null, section_header: null, page_number: null, table: "incident_logs", record_id: 4471 },
  ];
}

function answerFor(category: Category, mode: RetrievalMode): string {
  if (category === "incident") {
    return "This matches an active incident already logged for your region. I've escalated this with full context — the on-call team will follow up shortly.";
  }
  if (mode === "SQL") {
    return "Your account is active and in good standing. The charge you're asking about corresponds to a mid-cycle plan upgrade, prorated into this invoice.";
  }
  return "To rotate your API key: Account Settings → API Keys → Revoke, then issue a new one from the same panel. The old key stops working within a few seconds.";
}

function buildChatResponse(params: {
  conversationId: string;
  traceId: string;
  category: Category;
  severity: Severity;
  retrievalMode: RetrievalMode | null;
  confidenceScore: number | null;
  confidenceTier: ConfidenceTier | null;
  escalated: boolean;
  flaggedForReview: boolean;
  answer: string;
  sources: SourceRef[];
  retryCount: number;
  loopbackCount: number;
}): ChatResponse {
  return {
    answer: params.answer,
    category: params.category,
    severity: params.severity,
    retrieval_mode: params.retrievalMode,
    confidence_score: params.confidenceScore,
    confidence_tier: params.confidenceTier,
    sources: params.sources,
    escalated: params.escalated,
    flagged_for_review: params.flaggedForReview,
    trace_id: params.traceId,
    conversation_id: params.conversationId,
    retrieval_retry_count: params.retryCount,
    reflection_loopback_count: params.loopbackCount,
  };
}

export function buildMockChatFrames(body: ChatRequest): MockFrame[] {
  const q = body.query.toLowerCase();
  const conversationId = body.conversation_id ?? `conv_${randomSuffix()}`;
  const traceId = `lf_trace_${randomSuffix()}`;

  const wantsHuman = /\b(human|escalate|speak to|talk to)\b/.test(q);
  const isIncident = /\b(incident|outage|down|500s?|not working|critical)\b/.test(q);
  const isBilling = /\b(invoice|charge|billing|payment)\b/.test(q);
  const forceLoop = /\b(slow|unsure|not sure|confusing)\b/.test(q);

  const frames: MockFrame[] = [];

  if (wantsHuman) {
    frames.push({ event: "node", delayMs: 400, data: { node: "classify_node", category: "usage" } });
    frames.push({ event: "node", delayMs: 550, data: { node: "escalate_node", escalation_flag: true } });
    frames.push({
      event: "done",
      delayMs: 300,
      data: buildChatResponse({
        conversationId,
        traceId,
        category: "usage",
        severity: "Medium",
        retrievalMode: null,
        confidenceScore: null,
        confidenceTier: null,
        escalated: true,
        flaggedForReview: false,
        answer: "I've connected you with a human support agent — they'll follow up on this conversation shortly.",
        sources: [],
        retryCount: 0,
        loopbackCount: 0,
      }),
    });
    return frames;
  }

  const category: Category = isIncident ? "incident" : isBilling ? "billing" : "usage";
  const retrievalMode: RetrievalMode = isIncident ? "Hybrid" : isBilling ? "SQL" : "RAG";

  frames.push({ event: "node", delayMs: 350, data: { node: "classify_node", category } });
  frames.push({ event: "node", delayMs: 300, data: { node: "router_node", retrieval_mode: retrievalMode } });

  if (retrievalMode === "RAG") {
    frames.push({ event: "node", delayMs: 550, data: { node: "doc_retrieval_node" } });
  } else if (retrievalMode === "SQL") {
    frames.push({ event: "node", delayMs: 450, data: { node: "account_validation_node" } });
  } else {
    frames.push({ event: "node", delayMs: 550, data: { node: "doc_retrieval_node" } });
    frames.push({ event: "node", delayMs: 500, data: { node: "account_validation_node" } });
  }

  if (isIncident) {
    frames.push({ event: "node", delayMs: 450, data: { node: "incident_severity_node", severity_final: "High" } });
  }

  let confidenceScore = isBilling ? 0.78 : 0.92;
  let loopbackCount = 0;

  if (forceLoop) {
    frames.push({ event: "node", delayMs: 500, data: { node: "reflect_node", confidence_score: 0.58, confidence_tier: "Low" } });
    frames.push({ event: "node", delayMs: 550, data: { node: "doc_retrieval_node", retrieval_retry_count: 0 } });
    loopbackCount = 1;
    confidenceScore = 0.86;
  }

  const confidenceTier: ConfidenceTier = confidenceScore >= 0.85 ? "High" : confidenceScore >= 0.7 ? "Medium" : "Low";
  frames.push({
    event: "node",
    delayMs: 500,
    data: { node: "reflect_node", confidence_score: confidenceScore, confidence_tier: confidenceTier, reflection_loopback_count: loopbackCount },
  });

  const flaggedForReview = confidenceTier === "Medium";
  frames.push({ event: "node", delayMs: 350, data: { node: "respond_node" } });

  frames.push({
    event: "done",
    delayMs: 250,
    data: buildChatResponse({
      conversationId,
      traceId,
      category,
      severity: isIncident ? "High" : "Low",
      retrievalMode,
      confidenceScore,
      confidenceTier,
      escalated: false,
      flaggedForReview,
      answer: answerFor(category, retrievalMode),
      sources: sourcesFor(retrievalMode),
      retryCount: 0,
      loopbackCount,
    }),
  });

  return frames;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// A real backend persists the new turn immediately, so a subsequent
// GET /conversations/{id} right after sending succeeds. This mock needs
// the same fidelity — without it, a brand-new conversation_id the mock
// just invented has no matching MOCK_CONVERSATION_DETAILS entry, and the
// detail query ChatPage fires after navigating there 404s (harmless —
// skipNextHistoryLoadRef already means the UI doesn't depend on it — but
// a needless console 404 on the most common demo path is worth avoiding).
function registerConversationTurn(body: ChatRequest, response: ChatResponse): void {
  const now = new Date().toISOString();
  const userMessage: MessageOut = {
    role: "user",
    content: body.query,
    created_at: now,
    confidence_tier: null,
    sources: null,
    trace_id: response.trace_id,
    category: null,
    severity: null,
    retrieval_mode: null,
    confidence_score: null,
    flagged_for_review: false,
    escalated: false,
  };
  const assistantMessage: MessageOut = {
    role: "assistant",
    content: response.answer,
    created_at: now,
    confidence_tier: response.confidence_tier,
    sources: response.sources,
    trace_id: response.trace_id,
    category: response.category,
    severity: response.severity,
    retrieval_mode: response.retrieval_mode,
    confidence_score: response.confidence_score,
    flagged_for_review: response.flagged_for_review,
    escalated: response.escalated,
  };

  const existing = MOCK_CONVERSATION_DETAILS[response.conversation_id];
  if (existing) {
    existing.messages.push(userMessage, assistantMessage);
    const summary = MOCK_CONVERSATIONS.find((c) => c.conversation_id === response.conversation_id);
    if (summary) {
      summary.last_message_at = now;
      if (response.escalated) {
        summary.status = "escalated";
        summary.escalated = true;
      }
    }
    return;
  }

  MOCK_CONVERSATIONS.unshift({
    conversation_id: response.conversation_id,
    customer_id: body.customer_id,
    last_message_at: now,
    status: response.escalated ? "escalated" : "open",
    escalated: response.escalated,
  });
  MOCK_CONVERSATION_DETAILS[response.conversation_id] = {
    conversation_id: response.conversation_id,
    messages: [userMessage, assistantMessage],
  };
}

export function frameToSSE(frame: MockFrame): string {
  return `event: ${frame.event}\ndata: ${JSON.stringify(frame.data)}\n\n`;
}

export function mockChatStreamBody(body: ChatRequest): ReadableStream<Uint8Array> {
  const frames = buildMockChatFrames(body);
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const frame of frames) {
        await sleep(frame.delayMs);
        if (frame.event === "done") {
          registerConversationTurn(body, frame.data as ChatResponse);
        }
        controller.enqueue(encoder.encode(frameToSSE(frame)));
      }
      controller.close();
    },
  });
}
