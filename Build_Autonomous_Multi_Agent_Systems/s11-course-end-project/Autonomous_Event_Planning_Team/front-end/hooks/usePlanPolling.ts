"use client";

import { useEffect, useState } from "react";
import { getPlan } from "../lib/api";
import type { PlanResponse } from "../lib/types";

const POLL_INTERVAL_MS = 1500;
const TERMINAL_STATUSES = new Set(["completed", "needs_review", "failed"]);

interface UsePlanPollingResult {
  plan: PlanResponse | null;
  error: string | null;
  isPolling: boolean;
}

/**
 * Polls GET /plans/{id} until the plan reaches a terminal status. `pollKey`
 * lets a caller restart polling against the same planId (e.g. after
 * submitting a refine instruction) by incrementing it.
 */
export function usePlanPolling(planId: string | null, pollKey = 0): UsePlanPollingResult {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    if (!planId) {
      setPlan(null);
      setError(null);
      setIsPolling(false);
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    setIsPolling(true);
    setError(null);

    async function poll() {
      try {
        const result = await getPlan(planId as string);
        if (cancelled) return;

        setPlan(result);

        if (TERMINAL_STATUSES.has(result.status)) {
          setIsPolling(false);
          return;
        }

        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to fetch plan status.");
        setIsPolling(false);
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [planId, pollKey]);

  return { plan, error, isPolling };
}
