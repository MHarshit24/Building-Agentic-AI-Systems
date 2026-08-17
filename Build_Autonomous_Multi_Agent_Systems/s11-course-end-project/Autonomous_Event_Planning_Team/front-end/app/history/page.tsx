"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangleIcon, ArrowRightIcon } from "../../components/icons";
import { StatusBadge } from "../../components/StatusBadge";
import { ApiError, listPlans } from "../../lib/api";
import type { PlanSummary } from "../../lib/types";

export default function HistoryPage() {
  const [plans, setPlans] = useState<PlanSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    listPlans()
      .then((result) => {
        if (!cancelled) setPlans(result);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load plan history.");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="animate-fade-in">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink-800 sm:text-3xl">Plan history</h1>
        <p className="mt-1 text-sm text-ink-500">Every plan created on this backend, most recent first.</p>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-risk-200 bg-risk-50 p-4 text-sm text-risk-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!error && plans === null && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-32 animate-shimmer rounded-2xl border border-ink-100 bg-gradient-to-r from-white via-ink-50 to-white bg-[length:200%_100%]"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      )}

      {!error && plans !== null && plans.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ink-200 p-10 text-center text-sm text-ink-400">
          No plans yet.{" "}
          <Link href="/" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </Link>
          .
        </div>
      )}

      {!error && plans !== null && plans.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {plans.map((plan, index) => (
            <motion.li
              key={plan.plan_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03, duration: 0.3 }}
            >
              <Link
                href={`/history/${plan.plan_id}`}
                className="group flex h-full flex-col justify-between gap-3 rounded-2xl border border-ink-100 bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md"
              >
                <div className="min-w-0">
                  <p className="truncate font-display text-sm font-semibold text-ink-800">{plan.event_type}</p>
                  <p className="mt-0.5 truncate text-sm text-ink-400">{plan.objective}</p>
                  <p className="mt-1 text-xs text-ink-300">{formatDate(plan.created_at)}</p>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={plan.status} />
                    {plan.latest_score !== null && (
                      <span className="text-xs text-ink-400">score {plan.latest_score.toFixed(2)}</span>
                    )}
                  </div>
                  <ArrowRightIcon className="h-4 w-4 shrink-0 text-ink-200 transition-colors group-hover:text-brand-500" />
                </div>
              </Link>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
