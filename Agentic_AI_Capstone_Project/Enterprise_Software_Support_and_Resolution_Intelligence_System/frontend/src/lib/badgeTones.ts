// Split out of Badge.tsx: a component file may only export the component
// itself (react-refresh/only-export-components) or Fast Refresh breaks.

import type { BadgeTone } from "../components/ui/Badge";

export function toneForConfidenceTier(tier: string | null): BadgeTone {
  if (tier === "High") return "success";
  if (tier === "Medium") return "warning";
  if (tier === "Low") return "danger";
  return "neutral";
}

export function toneForSeverity(severity: string | null): BadgeTone {
  if (severity === "Critical") return "danger";
  if (severity === "High") return "warning";
  return "neutral";
}

export function toneForConversationStatus(status: string): BadgeTone {
  if (status === "escalated") return "escalate";
  if (status === "open" || status === "in_progress") return "info";
  if (status === "resolved" || status === "closed") return "success";
  return "neutral";
}
