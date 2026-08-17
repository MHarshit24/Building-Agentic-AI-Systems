// Single source of truth mapping each agent to a label/icon/color so the
// live agent graph, specialist badges, refine-form toggles, and the final
// blueprint's section headers all agree on "amber = logistics" etc.
// Tailwind's JIT scanner needs literal class strings (not dynamic
// `bg-${key}-100` concatenation), hence the explicit table below.

import type { ComponentType } from "react";
import type { SpecialistKey } from "../lib/types";
import { CalendarIcon, MegaphoneIcon, ShieldAlertIcon, SparkleIcon, VenueIcon, WalletIcon } from "./icons";

export type AgentKey = SpecialistKey | "manager";

interface AgentTheme {
  label: string;
  Icon: ComponentType<{ className?: string }>;
  chipBg: string;
  chipText: string;
  solidBg: string;
  solidText: string;
  border: string;
  ring: string;
  textStrong: string;
  glow: string;
}

export const AGENT_ORDER: SpecialistKey[] = ["logistics", "budget", "marketing", "schedule", "risk"];

export const AGENT_THEME: Record<AgentKey, AgentTheme> = {
  logistics: {
    label: "Logistics",
    Icon: VenueIcon,
    chipBg: "bg-logistics-100",
    chipText: "text-logistics-600",
    solidBg: "bg-logistics-500",
    solidText: "text-white",
    border: "border-logistics-200",
    ring: "ring-logistics-400",
    textStrong: "text-logistics-600",
    glow: "shadow-[0_0_0_4px_rgba(245,158,11,0.15)]",
  },
  budget: {
    label: "Budget",
    Icon: WalletIcon,
    chipBg: "bg-budget-100",
    chipText: "text-budget-600",
    solidBg: "bg-budget-500",
    solidText: "text-white",
    border: "border-budget-200",
    ring: "ring-budget-400",
    textStrong: "text-budget-600",
    glow: "shadow-[0_0_0_4px_rgba(16,185,129,0.15)]",
  },
  marketing: {
    label: "Marketing",
    Icon: MegaphoneIcon,
    chipBg: "bg-marketing-100",
    chipText: "text-marketing-600",
    solidBg: "bg-marketing-500",
    solidText: "text-white",
    border: "border-marketing-200",
    ring: "ring-marketing-400",
    textStrong: "text-marketing-600",
    glow: "shadow-[0_0_0_4px_rgba(217,70,239,0.15)]",
  },
  schedule: {
    label: "Schedule",
    Icon: CalendarIcon,
    chipBg: "bg-schedule-100",
    chipText: "text-schedule-600",
    solidBg: "bg-schedule-500",
    solidText: "text-white",
    border: "border-schedule-200",
    ring: "ring-schedule-400",
    textStrong: "text-schedule-600",
    glow: "shadow-[0_0_0_4px_rgba(14,165,233,0.15)]",
  },
  risk: {
    label: "Risk",
    Icon: ShieldAlertIcon,
    chipBg: "bg-risk-100",
    chipText: "text-risk-600",
    solidBg: "bg-risk-500",
    solidText: "text-white",
    border: "border-risk-200",
    ring: "ring-risk-400",
    textStrong: "text-risk-600",
    glow: "shadow-[0_0_0_4px_rgba(239,68,68,0.15)]",
  },
  manager: {
    label: "Manager",
    Icon: SparkleIcon,
    chipBg: "bg-manager-100",
    chipText: "text-manager-600",
    solidBg: "bg-manager-500",
    solidText: "text-white",
    border: "border-manager-200",
    ring: "ring-manager-400",
    textStrong: "text-manager-600",
    glow: "shadow-[0_0_0_4px_rgba(124,77,255,0.18)]",
  },
};
