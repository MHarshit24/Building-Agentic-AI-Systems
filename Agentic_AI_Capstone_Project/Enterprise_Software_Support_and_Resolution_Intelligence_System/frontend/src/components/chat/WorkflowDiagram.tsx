// SVG rendering of the REAL LangGraph topology (backend/app/orchestration/
// graph.py) — see the plan's Part 1 diagram, which replaces blueprint.md
// §11's stale version. Driven live by the actual SSE node events from
// POST /chat/stream (A6), not a client-side replay: each node lights up
// when its real event arrives.
//
// Agent vs. deterministic distinction (verified directly against the
// backend, not assumed): of the 9 real graph nodes, exactly 6 are genuine
// LLM agents — each has its own prompts/*_v1.py file and calls
// call_llm_structured (classify, doc_retrieval, account_validation,
// incident_severity, reflect, escalate). The other 3 — router_node,
// respond_node, out_of_scope_refusal_node — are plain deterministic
// Python with no LLM call at all (confirmed by reading each node's own
// docstring, e.g. respond.py: "Pure deterministic Python — no LLM call,
// no prompt file").
//
// Layout note: graph.py's _guard_structured_output wraps classify_node,
// doc_retrieval_node, account_validation_node and incident_severity_node
// so that ANY of them can route straight to escalate_node on a structured-
// output failure — a real edge in the graph, not an edge case worth
// hiding. Drawing all four as straight/diagonal lines converging on
// escalate_node crossed the whole diagram (the first attempt at this).
// Each one is instead routed as its own explicit elbow path — doc_retrieval
// shares escalate_node's own x-column so it's a plain vertical drop; the
// other three detour through a dedicated side lane at a height clear of
// every other node's row, so the line never cuts through a box, even
// though it does still visibly connect the two real nodes.

import { Bot, Cog } from "lucide-react";
import type { ChatStreamNodeEvent } from "../../api/types";

interface NodeSpec {
  id: string;
  label: string;
  agentName: string | null; // null => deterministic, no LLM call
  x: number;
  y: number;
}

interface EdgeSpec {
  from: string;
  to: string;
  /** Long dashes — reflect_node's own retry loop-back only. */
  dashed?: boolean;
  /** Fine dots — the 4 structured-output-error edges into escalate_node.
   * A visually distinct style from `dashed` so the two different meanings
   * ("this node retries" vs. "this node can escalate directly on error")
   * don't read as the same kind of edge. */
  dotted?: boolean;
  label?: string;
  /** Route as an elbow via a left-margin lane instead of a straight line,
   * to go around intervening nodes instead of through them. */
  laneX?: number;
  /** Fully explicit path, for edges a single lane can't route around other
   * nodes cleanly (see the 4 error-escalation edges below). Takes priority
   * over laneX/straight-line rendering when present. */
  customPath?: string;
}

const NODE_W = 156;
const NODE_H = 46;

const NODES: NodeSpec[] = [
  { id: "classify_node", label: "classify_node", agentName: "Intent Classification Agent", x: 390, y: 70 },
  { id: "out_of_scope_refusal_node", label: "out_of_scope_refusal_node", agentName: null, x: 180, y: 200 },
  { id: "router_node", label: "router_node", agentName: null, x: 390, y: 200 },
  { id: "doc_retrieval_node", label: "doc_retrieval_node", agentName: "Documentation Retrieval Agent", x: 180, y: 330 },
  { id: "account_validation_node", label: "account_validation_node", agentName: "Account Validation Agent", x: 600, y: 330 },
  { id: "incident_severity_node", label: "incident_severity_node", agentName: "Incident Severity Agent", x: 390, y: 460 },
  { id: "reflect_node", label: "reflect_node", agentName: "Reflection Agent", x: 390, y: 590 },
  { id: "escalate_node", label: "escalate_node", agentName: "Escalation Manager", x: 180, y: 720 },
  { id: "respond_node", label: "respond_node", agentName: null, x: 600, y: 720 },
  { id: "end", label: "END", agentName: null, x: 390, y: 840 },
];

const EDGES: EdgeSpec[] = [
  { from: "classify_node", to: "router_node", label: "in scope" },
  { from: "classify_node", to: "out_of_scope_refusal_node", label: "out of scope" },
  // Explicit-request / structured-output-error short circuit (_route_after_classify)
  // — routed around the whole diagram via the left margin instead of straight
  // through router_node/out_of_scope_refusal_node.
  { from: "classify_node", to: "escalate_node", dotted: true, customPath: "M 312 70 L 90 70 L 90 720 L 102 720" },
  { from: "router_node", to: "doc_retrieval_node", label: "RAG · Hybrid · Critical" },
  { from: "router_node", to: "account_validation_node", label: "SQL · Hybrid · Critical" },
  { from: "doc_retrieval_node", to: "incident_severity_node", label: "needs severity check" },
  { from: "doc_retrieval_node", to: "reflect_node" },
  // doc_retrieval_node already shares escalate_node's x-column, so its own
  // structured-output-error edge (_route_after_retrieval) is a plain drop.
  { from: "doc_retrieval_node", to: "escalate_node", dotted: true, customPath: "M 180 353 L 180 697" },
  { from: "account_validation_node", to: "incident_severity_node" },
  { from: "account_validation_node", to: "reflect_node" },
  {
    from: "account_validation_node",
    to: "escalate_node",
    dotted: true,
    customPath: "M 600 353 L 600 380 L 45 380 L 45 720 L 102 720",
  },
  { from: "incident_severity_node", to: "reflect_node" },
  {
    from: "incident_severity_node",
    to: "escalate_node",
    dotted: true,
    customPath: "M 390 483 L 390 520 L 75 520 L 75 720 L 102 720",
  },
  { from: "reflect_node", to: "doc_retrieval_node", dashed: true, label: "ungrounded, retry (≤1)", laneX: 60 },
  { from: "reflect_node", to: "escalate_node", label: "low confidence / critical" },
  { from: "reflect_node", to: "respond_node", label: "confident & grounded" },
  { from: "escalate_node", to: "end" },
  { from: "respond_node", to: "end" },
  { from: "out_of_scope_refusal_node", to: "end", laneX: 30 },
];

const NODE_BY_ID = new Map(NODES.map((n) => [n.id, n]));

type NodeState = "idle" | "active" | "done" | "escalate" | "error";

interface WorkflowDiagramProps {
  events: ChatStreamNodeEvent[];
  isComplete: boolean;
  hasError: boolean;
  escalated: boolean;
}

const NODE_STATE_CLASSES: Record<NodeState, string> = {
  idle: "fill-white stroke-flow-idle dark:fill-slate-800 dark:stroke-slate-600",
  active: "fill-brand-50 stroke-flow-active dark:fill-brand-950/60 animate-pulse-glow",
  done: "fill-green-50 stroke-flow-done dark:fill-green-950/40",
  escalate: "fill-purple-50 stroke-flow-escalate dark:fill-purple-950/40",
  error: "fill-red-50 stroke-flow-error dark:fill-red-950/40",
};

const NODE_TEXT_CLASSES: Record<NodeState, string> = {
  idle: "fill-slate-400 dark:fill-slate-500",
  active: "fill-flow-active font-semibold",
  done: "fill-flow-done font-semibold",
  escalate: "fill-flow-escalate font-semibold",
  error: "fill-flow-error font-semibold",
};

function edgeKey(from: string, to: string): string {
  return `${from}->${to}`;
}

/** Rough monospace-ish width estimate — good enough to size a legible
 * background rect behind a label without measuring text in the DOM. */
function estimateTextWidth(text: string, charWidth = 5.6): number {
  return text.length * charWidth + 10;
}

/** A straight source->target line. */
function straightPoints(from: NodeSpec, to: NodeSpec) {
  return {
    x1: from.x,
    y1: from.y + NODE_H / 2,
    x2: to.x,
    y2: to.y - NODE_H / 2,
  };
}

/** Routes around intervening nodes via a vertical lane hugging the left
 * margin, instead of a diagonal line straight through the diagram. */
function elbowLeftPath(from: NodeSpec, to: NodeSpec, laneX: number): string {
  const fx = from.x - NODE_W / 2;
  const fy = from.y;
  const tx = to.x - NODE_W / 2;
  const ty = to.y;
  return `M ${fx} ${fy} L ${laneX} ${fy} L ${laneX} ${ty} L ${tx} ${ty}`;
}

export function WorkflowDiagram({ events, isComplete, hasError, escalated }: WorkflowDiagramProps) {
  const sequence = events.map((e) => e.node);

  const nodeStates = new Map<string, NodeState>();
  sequence.forEach((id, idx) => {
    const isLast = idx === sequence.length - 1;
    let state: NodeState = "done";
    if (id === "escalate_node") state = "escalate";
    if (isLast && !isComplete && !hasError) state = "active";
    if (isLast && hasError) state = "error";
    nodeStates.set(id, state);
  });
  if (isComplete) {
    nodeStates.set("end", escalated ? "escalate" : "done");
  }

  // See this file's own header comment for why edges are derived from each
  // node's known real predecessor(s) rather than naive consecutive-event
  // adjacency (that approach broke on Hybrid/Critical's concurrent fan-out).
  const activeEdges = new Set<string>();
  const seenSoFar = new Set<string>();
  sequence.forEach((nodeId, idx) => {
    if (nodeId === "doc_retrieval_node") {
      const isFirstOccurrence = sequence.indexOf(nodeId) === idx;
      activeEdges.add(edgeKey(isFirstOccurrence ? "router_node" : "reflect_node", nodeId));
    } else if (nodeId === "account_validation_node") {
      activeEdges.add(edgeKey("router_node", nodeId));
    } else if (nodeId === "incident_severity_node" || (nodeId === "reflect_node" && !seenSoFar.has("incident_severity_node"))) {
      for (const source of ["doc_retrieval_node", "account_validation_node"]) {
        if (seenSoFar.has(source)) activeEdges.add(edgeKey(source, nodeId));
      }
    } else if (idx > 0) {
      activeEdges.add(edgeKey(sequence[idx - 1]!, nodeId));
    }
    seenSoFar.add(nodeId);
  });
  if (isComplete && sequence.length > 0) {
    activeEdges.add(edgeKey(sequence[sequence.length - 1]!, "end"));
  }

  const hasStarted = events.length > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* flex-1 + preserveAspectRatio="none": claims exactly the panel's
          leftover height (after the legend below), with zero blank margin
          either way. Unlike "meet" — which preserves the viewBox's own
          780:865 ratio and letterboxes whatever space that ratio doesn't
          use — "none" stretches the content to the assigned box exactly,
          so it always fills the panel to the legend's edge, at the cost of
          a small amount of non-uniform scaling. min-h-0 is required
          alongside flex-1: an SVG is a "replaced element", so its default
          min-height:auto (driven by the viewBox's intrinsic ratio) would
          otherwise refuse to shrink below that ratio and overflow the
          column regardless of preserveAspectRatio. */}
      <svg
        viewBox="0 15 780 865"
        className="w-full min-h-0 flex-1"
        preserveAspectRatio="none"
        role="img"
        aria-label="Agent workflow diagram"
      >
        <g strokeWidth={1.5}>
          {EDGES.map((edge) => {
            const from = NODE_BY_ID.get(edge.from)!;
            const to = NODE_BY_ID.get(edge.to)!;
            const isActive = activeEdges.has(edgeKey(edge.from, edge.to));
            const colorClass = isActive
              ? "stroke-flow-active transition-colors duration-300"
              : "stroke-slate-200 transition-colors duration-300 dark:stroke-slate-700";
            const textColorClass = isActive ? "fill-flow-active font-medium" : "fill-slate-400 dark:fill-slate-500";
            const dashArray = edge.dashed ? "5 4" : edge.dotted ? "1.5 3" : undefined;

            let labelX: number;
            let labelY: number;
            if (edge.laneX != null) {
              labelX = (edge.laneX + (from.x - NODE_W / 2)) / 2;
              labelY = from.y;
            } else {
              labelX = (from.x + to.x) / 2;
              labelY = (from.y + to.y) / 2;
            }
            const labelWidth = edge.label ? estimateTextWidth(edge.label) : 0;

            return (
              <g key={edgeKey(edge.from, edge.to)}>
                {edge.customPath ? (
                  <path d={edge.customPath} fill="none" className={colorClass} strokeDasharray={dashArray} />
                ) : edge.laneX != null ? (
                  <path d={elbowLeftPath(from, to, edge.laneX)} fill="none" className={colorClass} strokeDasharray={dashArray} />
                ) : (
                  <line {...straightPoints(from, to)} className={colorClass} strokeDasharray={dashArray} />
                )}
                {edge.label && (
                  <g>
                    <rect x={labelX - labelWidth / 2} y={labelY - 7} width={labelWidth} height={14} className="fill-white dark:fill-slate-900" />
                    <text x={labelX} y={labelY} textAnchor="middle" dominantBaseline="middle" className={`text-[9px] transition-colors duration-300 ${textColorClass}`}>
                      {edge.label}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>

        {NODES.map((node) => {
          const state = nodeStates.get(node.id) ?? "idle";
          const isAgent = node.agentName !== null;
          const captionText = isAgent ? node.agentName! : "deterministic — no LLM call";
          const captionCharWidth = isAgent ? 5.3 : 4.7;
          const captionTextWidth = captionText.length * captionCharWidth;
          const iconSize = 11;
          const gap = 4;
          const captionTotalWidth = iconSize + gap + captionTextWidth;
          const captionStartX = -captionTotalWidth / 2;
          const CaptionIcon = isAgent ? Bot : Cog;

          return (
            <g key={node.id} className="transition-transform duration-300">
              {/* Caption above the box — agent name for real LLM agents, an
                  explicit "no LLM call" note for deterministic nodes, laid
                  out as icon+text with an explicit combined width so the two
                  never overlap. */}
              <g transform={`translate(${node.x}, ${node.y - NODE_H / 2 - 14})`}>
                <CaptionIcon
                  size={iconSize}
                  x={captionStartX}
                  y={-iconSize / 2}
                  className={isAgent ? "fill-none stroke-brand-500 dark:stroke-brand-400" : "fill-none stroke-slate-400"}
                />
                <text
                  x={captionStartX + iconSize + gap}
                  y={0}
                  textAnchor="start"
                  dominantBaseline="middle"
                  className={`text-[9.5px] ${isAgent ? "fill-brand-600 font-medium dark:fill-brand-400" : "fill-slate-400 italic"}`}
                >
                  {captionText}
                </text>
              </g>

              <rect
                x={node.x - NODE_W / 2}
                y={node.y - NODE_H / 2}
                width={NODE_W}
                height={NODE_H}
                rx={node.id === "end" ? NODE_H / 2 : 8}
                className={`transition-colors duration-300 ${NODE_STATE_CLASSES[state]}`}
                strokeWidth={state === "idle" ? 1.5 : 2}
                strokeDasharray={isAgent ? undefined : "4 3"}
              />
              <text
                x={node.x}
                y={node.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className={`text-[11px] transition-colors duration-300 ${NODE_TEXT_CLASSES[state]}`}
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 border-t border-slate-100 px-2 py-2 text-[10px] text-slate-400 dark:border-slate-800">
        <span className="flex items-center gap-1">
          <Bot size={11} className="stroke-brand-500 dark:stroke-brand-400" /> LLM agent
        </span>
        <span className="flex items-center gap-1">
          <Cog size={11} /> deterministic (no LLM)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0 w-4 border-t border-dashed border-slate-400" /> retry loop-back
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0 w-4 border-t-2 border-dotted border-slate-400" /> can escalate directly on invalid output
        </span>
      </div>

      {!hasStarted && (
        <p className="pb-2 text-center text-xs text-slate-400">Send a message to watch the agent workflow run.</p>
      )}
    </div>
  );
}
