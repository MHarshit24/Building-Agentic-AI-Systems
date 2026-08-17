import { AlertTriangle } from "lucide-react";

export function EscalationBanner() {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-xs font-medium text-purple-800 dark:border-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
      <AlertTriangle size={14} className="shrink-0" />
      <span>Escalated to a human support agent — they'll follow up with full context.</span>
    </div>
  );
}
