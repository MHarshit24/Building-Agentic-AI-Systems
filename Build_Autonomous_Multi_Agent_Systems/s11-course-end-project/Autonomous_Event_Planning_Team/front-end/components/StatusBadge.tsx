const STATUS_STYLES: Record<string, string> = {
  completed: "bg-budget-100 text-budget-600",
  needs_review: "bg-logistics-100 text-logistics-600",
  failed: "bg-risk-100 text-risk-600",
  in_progress: "bg-brand-100 text-brand-600",
};

const STATUS_LABELS: Record<string, string> = {
  completed: "Completed",
  needs_review: "Needs review",
  failed: "Failed",
  in_progress: "In progress",
};

const STATUS_DOT: Record<string, string> = {
  completed: "bg-budget-500",
  needs_review: "bg-logistics-500",
  failed: "bg-risk-500",
  in_progress: "bg-brand-500 animate-pulse",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status] ?? "bg-ink-100 text-ink-600"}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status] ?? "bg-ink-400"}`} />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
