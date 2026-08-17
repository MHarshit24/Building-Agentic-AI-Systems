import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, PanelRightClose, PanelRightOpen } from "lucide-react";
import { getConversation, listConversations } from "../api/endpoints";
import { streamChat } from "../api/chatStream";
import type { ChatResponse, ChatStreamNodeEvent, CustomerSummary, MessageOut } from "../api/types";
import { MessageThread } from "../components/chat/MessageThread";
import { ChatInput } from "../components/chat/ChatInput";
import { WorkflowDiagram } from "../components/chat/WorkflowDiagram";
import { CustomerPicker } from "../components/chat/CustomerPicker";
import type { ChatMessageVM } from "../components/chat/MessageBubble";
import type { ReasoningTraceData } from "../components/chat/ReasoningTraceDropdown";

function toVMFromChatResponse(response: ChatResponse): ChatMessageVM {
  const trace: ReasoningTraceData = {
    category: response.category,
    severity: response.severity,
    retrieval_mode: response.retrieval_mode,
    confidence_score: response.confidence_score,
    confidence_tier: response.confidence_tier,
    flagged_for_review: response.flagged_for_review,
    trace_id: response.trace_id,
    retrieval_retry_count: response.retrieval_retry_count,
    reflection_loopback_count: response.reflection_loopback_count,
  };
  return {
    id: response.trace_id,
    role: "assistant",
    content: response.answer,
    sources: response.sources,
    escalated: response.escalated,
    trace,
  };
}

function toVMFromMessageOut(message: MessageOut, index: number): ChatMessageVM {
  const trace: ReasoningTraceData | undefined =
    message.role === "assistant"
      ? {
          category: message.category,
          severity: message.severity,
          retrieval_mode: message.retrieval_mode,
          confidence_score: message.confidence_score,
          confidence_tier: message.confidence_tier,
          flagged_for_review: message.flagged_for_review,
          trace_id: message.trace_id,
        }
      : undefined;
  return {
    id: `${message.trace_id ?? "msg"}-${index}`,
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    sources: message.sources ?? undefined,
    escalated: message.role === "assistant" ? message.escalated : undefined,
    trace,
  };
}

type StreamStatus = "idle" | "streaming" | "done" | "error";

const SHOW_DIAGRAM_STORAGE_KEY = "esri_show_workflow_diagram";

function readShowDiagramPreference(): boolean {
  const stored = window.localStorage.getItem(SHOW_DIAGRAM_STORAGE_KEY);
  return stored === null ? true : stored === "true";
}

export default function ChatPage() {
  const { conversationId: routeConversationId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [messages, setMessages] = useState<ChatMessageVM[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null);
  const [liveEvents, setLiveEvents] = useState<ChatStreamNodeEvent[]>([]);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  // Not all users want the workflow diagram visible every time — this only
  // controls whether the panel is RENDERED, never whether events are
  // tracked. liveEvents above lives in this component regardless, so
  // toggling this back on always shows the diagram fully caught up, not
  // reset to blank.
  const [showDiagram, setShowDiagram] = useState<boolean>(readShowDiagramPreference);

  useEffect(() => {
    window.localStorage.setItem(SHOW_DIAGRAM_STORAGE_KEY, String(showDiagram));
  }, [showDiagram]);

  // Set right before we navigate to a freshly-created conversation's own
  // URL after a successful send — skips the next history reload, since
  // `messages` already holds the correct content and a reload would just
  // be redundant (or worse, a network hiccup away from briefly clearing it).
  const skipNextHistoryLoadRef = useRef(false);

  // ConversationDetailResponse (GET /conversations/{id}) doesn't include
  // customer_id — only ConversationSummary (GET /conversations) does. This
  // list lookup is how an existing conversation's customer_id is resolved
  // to keep sending further turns in it.
  const { data: conversationsData } = useQuery({
    queryKey: ["conversations", true],
    queryFn: () => listConversations({ include_archived: true }),
  });

  const { data: detailData } = useQuery({
    queryKey: ["conversation-detail", routeConversationId],
    queryFn: () => getConversation(routeConversationId!),
    enabled: !!routeConversationId,
  });

  // Reset/populate `messages` when routeConversationId changes (switching
  // conversations, landing on "/", or history arriving for the current
  // one). This genuinely needs an effect, not React's render-time
  // "adjusting state when a prop changes" escape hatch: that pattern
  // forbids touching a ref during render, but skipNextHistoryLoadRef is
  // exactly what distinguishes "conversationId changed because the user
  // clicked a different conversation" (must reset) from "conversationId
  // changed because WE just navigated here after a successful send" (must
  // NOT reset — messages already holds the correct content). Both
  // reconciliation strategies React's docs suggest conflict with each
  // other in this specific case, so this is a deliberate, narrow
  // suppression rather than a restructure that would be more fragile.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (skipNextHistoryLoadRef.current) {
      skipNextHistoryLoadRef.current = false;
      return;
    }
    if (!routeConversationId) {
      setMessages([]);
      setSelectedCustomer(null);
      return;
    }
    if (detailData && detailData.conversation_id === routeConversationId) {
      setMessages(detailData.messages.map(toVMFromMessageOut));
    }
  }, [routeConversationId, detailData]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const existingCustomerId = useMemo(() => {
    if (!routeConversationId) return null;
    return conversationsData?.conversations.find((c) => c.conversation_id === routeConversationId)?.customer_id ?? null;
  }, [routeConversationId, conversationsData]);

  const isNewChat = !routeConversationId;
  const effectiveCustomerId = isNewChat ? (selectedCustomer?.customer_id ?? null) : existingCustomerId;
  const isStreaming = streamStatus === "streaming";
  const blockedReason = effectiveCustomerId == null ? "Select a customer above to start chatting." : undefined;

  async function handleSend(text: string) {
    if (effectiveCustomerId == null) return;

    const userMessage: ChatMessageVM = { id: crypto.randomUUID(), role: "user", content: text };
    const pendingAssistant: ChatMessageVM = { id: "pending-assistant", role: "assistant", content: "", pending: true };
    setMessages((prev) => [...prev, userMessage, pendingAssistant]);
    setLiveEvents([]);
    setStreamStatus("streaming");
    setStreamError(null);

    try {
      let finalResponse: ChatResponse | null = null;
      for await (const frame of streamChat({
        query: text,
        customer_id: effectiveCustomerId,
        conversation_id: routeConversationId ?? null,
      })) {
        if (frame.event === "node") {
          setLiveEvents((prev) => [...prev, frame.data]);
        } else if (frame.event === "done") {
          finalResponse = frame.data;
        } else if (frame.event === "error") {
          setStreamError(frame.data.message);
          setStreamStatus("error");
        }
      }

      if (finalResponse) {
        const assistantVM = toVMFromChatResponse(finalResponse);
        setMessages((prev) => [...prev.slice(0, -1), assistantVM]);
        setStreamStatus("done");
        queryClient.invalidateQueries({ queryKey: ["conversations"] });

        if (isNewChat) {
          skipNextHistoryLoadRef.current = true;
          navigate(`/chat/${finalResponse.conversation_id}`, { replace: true });
        } else {
          queryClient.invalidateQueries({ queryKey: ["conversation-detail", routeConversationId] });
        }
      }
    } catch (err) {
      setStreamStatus("error");
      setStreamError(err instanceof Error ? err.message : "Something went wrong sending this message.");
      setMessages((prev) => prev.slice(0, -1));
    }
  }

  const lastMessage = messages[messages.length - 1];
  const isEscalatedTurn = streamStatus === "done" && lastMessage?.role === "assistant" && !!lastMessage.escalated;

  return (
    <div className={`grid h-full grid-cols-1 ${showDiagram ? "lg:grid-cols-[1.5fr_1fr]" : "lg:grid-cols-[1fr_auto]"}`}>
      <div className="flex h-full flex-col overflow-hidden">
        {isNewChat && (
          <div className="border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-700 dark:bg-slate-900">
            <div className="max-w-xs">
              <CustomerPicker
                value={selectedCustomer}
                onChange={setSelectedCustomer}
                disabled={messages.length > 0}
              />
            </div>
          </div>
        )}

        <MessageThread messages={messages} />

        {streamError && (
          <div className="flex items-center gap-2 border-t border-red-200 bg-red-50/80 px-6 py-2 text-xs font-medium text-red-700 dark:border-red-900 dark:bg-red-900/20 dark:text-red-400">
            <AlertCircle size={14} className="shrink-0" />
            {streamError}
          </div>
        )}

        <ChatInput onSend={handleSend} disabled={isStreaming} blockedReason={blockedReason} />
      </div>

      {showDiagram ? (
        <div className="hidden overflow-y-auto border-l border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900 lg:flex lg:flex-col">
          <div className="mb-2 flex shrink-0 items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Agent Workflow</h2>
            <button
              type="button"
              onClick={() => setShowDiagram(false)}
              title="Hide workflow diagram"
              className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
            >
              <PanelRightClose size={16} />
            </button>
          </div>
          <WorkflowDiagram
            events={liveEvents}
            isComplete={streamStatus === "done" || streamStatus === "error"}
            hasError={streamStatus === "error"}
            escalated={isEscalatedTurn}
          />
        </div>
      ) : (
        <div className="hidden border-l border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900 lg:flex lg:flex-col lg:items-center">
          <button
            type="button"
            onClick={() => setShowDiagram(true)}
            title="Show workflow diagram"
            className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
          >
            <PanelRightOpen size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
