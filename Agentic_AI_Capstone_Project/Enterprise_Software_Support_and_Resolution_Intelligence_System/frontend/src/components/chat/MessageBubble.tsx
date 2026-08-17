import type { ReactNode } from "react";
import { SourceCitations } from "./SourceCitations";
import { ReasoningTraceDropdown, type ReasoningTraceData } from "./ReasoningTraceDropdown";
import { EscalationBanner } from "./EscalationBanner";
import type { SourceRef } from "../../api/types";

export interface ChatMessageVM {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceRef[];
  escalated?: boolean;
  trace?: ReasoningTraceData;
  pending?: boolean;
}

interface MessageBubbleProps {
  message: ChatMessageVM;
  children?: ReactNode;
}

export function MessageBubble({ message, children }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "bg-gradient-brand text-white shadow-sm shadow-brand-600/20"
            : "border border-slate-200 bg-white text-slate-800 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
        }`}
      >
        {message.content ? <p className="whitespace-pre-wrap">{message.content}</p> : children}

        {!isUser && message.escalated && (
          <div className="mt-2">
            <EscalationBanner />
          </div>
        )}
        {!isUser && message.sources && <SourceCitations sources={message.sources} />}
        {!isUser && message.trace && <ReasoningTraceDropdown trace={message.trace} />}
      </div>
    </div>
  );
}
