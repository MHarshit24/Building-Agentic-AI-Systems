"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AGENT_ORDER, AGENT_THEME } from "./agentTheme";
import { CheckCircleIcon, SpinnerIcon } from "./icons";
import type { PlanResponse, SpecialistKey } from "../lib/types";

// "working" = actively being (re)computed right now (spinner shown).
// "waiting" = this agent's own output is ready, but the round isn't over —
// other agents in the same iteration are still working (icon + small
// check badge, softly pulsing). Collapsing these two into one "active"
// state (as an earlier version of this component did) made a specialist
// that already finished look identical to one still computing.
type NodeState = "pending" | "working" | "waiting" | "active" | "done";

interface AgentGraphProps {
  plan: PlanResponse;
}

// Shared percentage coordinate space (0-100 on both axes) used by both the
// SVG connector layer (viewBox="0 0 100 100" preserveAspectRatio="none")
// and the absolutely-positioned HTML node badges, so the two layers always
// line up regardless of the container's actual rendered size.
const MANAGER_POS = { x: 50, y: 13 };
const REVIEWER_POS = { x: 50, y: 87 };
const SPECIALIST_X: Record<SpecialistKey, number> = {
  logistics: 10,
  budget: 30,
  marketing: 50,
  schedule: 70,
  risk: 90,
};
const SPECIALIST_Y = 50;

function curve(x1: number, y1: number, x2: number, y2: number): string {
  const midY = (y1 + y2) / 2;
  return `M ${x1} ${y1} Q ${x1} ${midY} ${(x1 + x2) / 2} ${midY} T ${x2} ${y2}`;
}

export function AgentGraph({ plan }: AgentGraphProps) {
  const activeSet = new Set(plan.active_revision_targets);
  const readySet = new Set(plan.specialist_outputs_ready);
  const isTerminal = plan.status !== "in_progress";

  const specialistState = (key: SpecialistKey): NodeState => {
    if (isTerminal) return "done";
    if (activeSet.has(key)) return readySet.has(key) ? "waiting" : "working";
    if (readySet.has(key)) return "done";
    return "pending";
  };

  const activeReady = AGENT_ORDER.filter((k) => activeSet.has(k) && readySet.has(k));
  const allActiveReady = activeSet.size > 0 && activeReady.length === activeSet.size;

  const managerState: NodeState = isTerminal
    ? "done"
    : activeSet.size > 0 && activeReady.length === 0
      ? "active"
      : "done";

  const reviewerState: NodeState = isTerminal ? "done" : allActiveReady ? "active" : "pending";

  const showLoop = !isTerminal && plan.iteration_count > 1;

  return (
    <div className="relative h-[280px] w-full sm:h-[340px] lg:h-[400px]">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden="true">
        {AGENT_ORDER.map((key) => {
          const x = SPECIALIST_X[key];
          const inFlow = specialistState(key) === "working" || managerState === "active";
          return (
            <path
              key={`m-${key}`}
              d={curve(MANAGER_POS.x, MANAGER_POS.y, x, SPECIALIST_Y)}
              fill="none"
              stroke={inFlow ? "#7C4DFF" : "#D6D3E6"}
              strokeWidth={inFlow ? 0.6 : 0.4}
              strokeDasharray={inFlow ? "3 2" : "0"}
              className={inFlow ? "animate-flow-dash" : ""}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
        {AGENT_ORDER.map((key) => {
          const x = SPECIALIST_X[key];
          const inFlow = readySet.has(key) && reviewerState === "active";
          return (
            <path
              key={`r-${key}`}
              d={curve(x, SPECIALIST_Y, REVIEWER_POS.x, REVIEWER_POS.y)}
              fill="none"
              stroke={inFlow ? "#7C4DFF" : "#D6D3E6"}
              strokeWidth={inFlow ? 0.6 : 0.4}
              strokeDasharray={inFlow ? "3 2" : "0"}
              className={inFlow ? "animate-flow-dash" : ""}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
        {showLoop && (
          <path
            d={`M ${REVIEWER_POS.x + 4} ${REVIEWER_POS.y} Q 108 50 ${MANAGER_POS.x + 4} ${MANAGER_POS.y}`}
            fill="none"
            stroke="#D946EF"
            strokeWidth="0.6"
            strokeDasharray="3 2"
            className="animate-flow-dash"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      <AgentNode pos={MANAGER_POS} agentKey="manager" state={managerState} sublabel="Planning" />
      {AGENT_ORDER.map((key) => (
        <AgentNode key={key} pos={{ x: SPECIALIST_X[key], y: SPECIALIST_Y }} agentKey={key} state={specialistState(key)} />
      ))}
      <AgentNode
        pos={REVIEWER_POS}
        agentKey="manager"
        state={reviewerState}
        sublabel="Reviewing"
        overrideLabel="Reviewer"
      />

      {showLoop && (
        <div
          className="absolute -translate-y-1/2 rounded-full bg-marketing-100 px-2 py-0.5 text-[10px] font-medium text-marketing-600"
          style={{ left: "96%", top: "50%" }}
        >
          revising
        </div>
      )}
    </div>
  );
}

function AgentNode({
  pos,
  agentKey,
  state,
  sublabel,
  overrideLabel,
}: {
  pos: { x: number; y: number };
  agentKey: keyof typeof AGENT_THEME;
  state: NodeState;
  sublabel?: string;
  overrideLabel?: string;
}) {
  const theme = AGENT_THEME[agentKey];
  const Icon = theme.Icon;
  const isPulsing = state === "active" || state === "working" || state === "waiting";
  const isSpinning = state === "active" || state === "working";

  return (
    <div
      className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5"
      style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
    >
      <div className="relative flex h-12 w-12 items-center justify-center sm:h-14 sm:w-14 lg:h-16 lg:w-16">
        <AnimatePresence>
          {isPulsing && (
            <motion.span
              key="ring"
              initial={{ opacity: 0 }}
              animate={{ opacity: state === "waiting" ? 0.5 : 1 }}
              exit={{ opacity: 0 }}
              className={`absolute inset-0 rounded-full ${theme.solidBg} animate-pulse-ring`}
            />
          )}
        </AnimatePresence>
        <motion.div
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 20 }}
          className={`relative flex h-11 w-11 items-center justify-center rounded-full border-2 transition-colors duration-500 sm:h-12 sm:w-12 lg:h-14 lg:w-14 ${
            state === "pending"
              ? "border-ink-200 bg-white text-ink-300"
              : `${theme.border} bg-white ${theme.textStrong}`
          }`}
        >
          {state === "done" ? (
            <CheckCircleIcon className={`h-6 w-6 animate-pop-in ${theme.textStrong}`} />
          ) : isSpinning ? (
            <SpinnerIcon className="h-5 w-5" />
          ) : (
            <Icon className="h-5 w-5 sm:h-6 sm:w-6" />
          )}
          {state === "waiting" && (
            <span
              className={`absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white ${theme.solidBg}`}
            >
              <CheckCircleIcon className="h-3.5 w-3.5 text-white" />
            </span>
          )}
        </motion.div>
      </div>
      <div className="text-center leading-tight">
        <p className={`text-[11px] font-semibold sm:text-xs ${state === "pending" ? "text-ink-300" : "text-ink-700"}`}>
          {overrideLabel ?? theme.label}
        </p>
        {sublabel && isSpinning && <p className="text-[10px] text-ink-400">{sublabel}</p>}
        {state === "waiting" && <p className="text-[10px] text-ink-400">Done, waiting...</p>}
      </div>
    </div>
  );
}
