import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "../ui/Badge";
import { toneForConfidenceTier, toneForSeverity } from "../../lib/badgeTones";

// Unified shape for both the just-answered turn (from ChatResponse) and a
// historical message (from MessageOut, A3) — retry/loop-back counts are
// only ever present for the live turn (not persisted per-message), so
// they're optional and simply omitted from the historical view.
export interface ReasoningTraceData {
  category: string | null;
  severity: string | null;
  retrieval_mode: string | null;
  confidence_score: number | null;
  confidence_tier: string | null;
  flagged_for_review: boolean;
  trace_id: string | null;
  retrieval_retry_count?: number;
  reflection_loopback_count?: number;
}

export function ReasoningTraceDropdown({ trace }: { trace: ReasoningTraceData }) {
  const [open, setOpen] = useState(false);
  if (!trace.category && !trace.confidence_tier) return null;

  return (
    <div className="mt-2 rounded-lg border border-slate-200 dark:border-slate-700">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"
      >
        <span>Reasoning trace</span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-slate-200 px-3 py-2 text-xs dark:border-slate-700">
          <div className="flex flex-wrap gap-1.5">
            {trace.category && <Badge tone="neutral">Category: {trace.category}</Badge>}
            {trace.severity && <Badge tone={toneForSeverity(trace.severity)}>Severity: {trace.severity}</Badge>}
            {trace.retrieval_mode && <Badge tone="info">Route: {trace.retrieval_mode}</Badge>}
            {trace.confidence_tier && (
              <Badge tone={toneForConfidenceTier(trace.confidence_tier)}>Confidence: {trace.confidence_tier}</Badge>
            )}
            {trace.flagged_for_review && <Badge tone="warning">Flagged for QA review</Badge>}
          </div>

          {trace.confidence_score != null && (
            <div>
              <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                <span>Confidence score</span>
                <span>{(trace.confidence_score * 100).toFixed(0)}%</span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                <div
                  className="bg-gradient-brand h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${Math.min(100, trace.confidence_score * 100)}%` }}
                />
              </div>
            </div>
          )}

          {(trace.retrieval_retry_count != null || trace.reflection_loopback_count != null) && (
            <div className="flex gap-3 text-slate-500 dark:text-slate-400">
              {trace.retrieval_retry_count != null && <span>Retrieval retries: {trace.retrieval_retry_count}</span>}
              {trace.reflection_loopback_count != null && (
                <span>Reflection loop-backs: {trace.reflection_loopback_count}</span>
              )}
            </div>
          )}

          {trace.trace_id && (
            <div className="truncate text-slate-400" title={trace.trace_id}>
              trace_id: {trace.trace_id}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
