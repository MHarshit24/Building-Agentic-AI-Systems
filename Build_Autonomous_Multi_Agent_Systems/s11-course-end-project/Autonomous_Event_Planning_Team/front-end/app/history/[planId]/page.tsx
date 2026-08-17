"use client";

import Link from "next/link";
import { useState } from "react";
import { BlueprintView } from "../../../components/BlueprintView";
import { AlertTriangleIcon } from "../../../components/icons";
import { ProgressPanel } from "../../../components/ProgressPanel";
import { RefineForm } from "../../../components/RefineForm";
import { usePlanPolling } from "../../../hooks/usePlanPolling";
import { ApiError, refinePlan } from "../../../lib/api";

const TERMINAL_STATUSES = new Set(["completed", "needs_review", "failed"]);

export default function PlanHistoryDetailPage({ params }: { params: { planId: string } }) {
  const [pollKey, setPollKey] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { plan, error: pollError, isPolling } = usePlanPolling(params.planId, pollKey);

  async function handleRefine(instruction: string, targetAgents: string[] | null) {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await refinePlan(params.planId, instruction, targetAgents);
      setPollKey((key) => key + 1);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to submit revision.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const isTerminal = plan !== null && TERMINAL_STATUSES.has(plan.status);

  return (
    <div className="space-y-6">
      <Link href="/history" className="text-sm font-medium text-ink-400 transition-colors hover:text-ink-700">
        &larr; Back to history
      </Link>

      {pollError && (
        <div className="flex items-start gap-2 rounded-xl border border-risk-200 bg-risk-50 p-4 text-sm text-risk-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{pollError}</span>
        </div>
      )}

      {submitError && (
        <div className="flex items-start gap-2 rounded-xl border border-risk-200 bg-risk-50 p-4 text-sm text-risk-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      {plan?.status === "failed" && (
        <div className="flex items-start gap-2 rounded-xl border border-risk-200 bg-risk-50 p-4 text-sm text-risk-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{plan.error_message ?? "Plan generation failed."}</span>
        </div>
      )}

      {plan && !isTerminal && <ProgressPanel plan={plan} />}

      {plan && isTerminal && plan.blueprint && (
        <>
          <BlueprintView
            blueprint={plan.blueprint}
            status={plan.status}
            critiqueHistory={plan.critique_history}
            qualityGateThreshold={plan.quality_gate_threshold}
            provider={plan.provider}
          />
          <RefineForm onSubmit={handleRefine} disabled={isSubmitting || isPolling} />
        </>
      )}

      {!plan && !pollError && <p className="text-sm text-ink-400">Loading...</p>}
    </div>
  );
}
