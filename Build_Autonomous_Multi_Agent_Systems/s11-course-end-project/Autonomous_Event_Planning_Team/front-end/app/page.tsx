"use client";

import { useState } from "react";
import { AGENT_ORDER, AGENT_THEME } from "../components/agentTheme";
import { BlueprintView } from "../components/BlueprintView";
import { BriefForm } from "../components/BriefForm";
import { AlertTriangleIcon } from "../components/icons";
import { ProgressPanel } from "../components/ProgressPanel";
import { RefineForm } from "../components/RefineForm";
import { usePlanPolling } from "../hooks/usePlanPolling";
import { ApiError, createPlan, refinePlan } from "../lib/api";
import type { EventBrief } from "../lib/types";

const CREW_BLURBS: Record<(typeof AGENT_ORDER)[number], string> = {
  logistics: "Venue, capacity, catering, vendors, and equipment.",
  budget: "Cost breakdown, budget fit, and cut recommendations.",
  marketing: "Channels, outreach timing, and a content calendar.",
  schedule: "Milestones from kickoff through event day.",
  risk: "Likely risks, impact, and mitigation plans.",
};

const TERMINAL_STATUSES = new Set(["completed", "needs_review", "failed"]);

export default function HomePage() {
  const [planId, setPlanId] = useState<string | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { plan, error: pollError, isPolling } = usePlanPolling(planId, pollKey);

  async function handleCreatePlan(brief: EventBrief) {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createPlan(brief);
      setPlanId(created.plan_id);
      setPollKey((key) => key + 1);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to create plan.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRefine(instruction: string, targetAgents: string[] | null) {
    if (!planId) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await refinePlan(planId, instruction, targetAgents);
      setPollKey((key) => key + 1);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to submit revision.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleStartOver() {
    setPlanId(null);
    setSubmitError(null);
  }

  const isTerminal = plan !== null && TERMINAL_STATUSES.has(plan.status);

  if (!planId) {
    return (
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:items-start lg:gap-14">
        <div className="animate-fade-in space-y-8 lg:sticky lg:top-10">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-800 sm:text-4xl lg:text-5xl">
              Plan an event with a{" "}
              <span className="text-gradient bg-[length:200%_100%] animate-gradient-x">crew of AI specialists</span>
            </h1>
            <p className="mt-3 text-sm text-ink-500 sm:text-base lg:text-lg">
              Submit a brief and watch logistics, budget, marketing, schedule, and risk agents build and review a
              full plan together, live.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {AGENT_ORDER.map((key, index) => {
              const theme = AGENT_THEME[key];
              const Icon = theme.Icon;
              const isLastOdd = AGENT_ORDER.length % 2 === 1 && index === AGENT_ORDER.length - 1;
              return (
                <div
                  key={key}
                  className={`flex items-start gap-3 rounded-xl border border-ink-100 bg-white p-4 shadow-sm ${isLastOdd ? "sm:col-span-2" : ""}`}
                >
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${theme.chipBg} ${theme.chipText}`}>
                    <Icon className="h-4.5 w-4.5" />
                  </span>
                  <div>
                    <p className="font-display text-sm font-semibold text-ink-800">{theme.label}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-400">{CREW_BLURBS[key]}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {submitError && <ErrorBanner message={submitError} />}
        </div>

        <BriefForm onSubmit={handleCreatePlan} disabled={isSubmitting} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {pollError && <ErrorBanner message={pollError} />}
      {plan?.status === "failed" && (
        <ErrorBanner message={plan.error_message ?? "Plan generation failed."} />
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

      <button
        type="button"
        onClick={handleStartOver}
        className="text-sm font-medium text-ink-400 transition-colors hover:text-ink-700"
      >
        &larr; Start a new plan
      </button>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex animate-fade-slide-in items-start gap-2 rounded-xl border border-risk-200 bg-risk-50 p-4 text-sm text-risk-700">
      <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
