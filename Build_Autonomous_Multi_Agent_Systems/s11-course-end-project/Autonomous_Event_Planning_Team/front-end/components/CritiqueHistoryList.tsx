import type { CritiqueNote, SpecialistKey } from "../lib/types";
import { AGENT_THEME } from "./agentTheme";

interface CritiqueHistoryListProps {
  history: CritiqueNote[];
  threshold: number;
}

const DIMENSION_LABELS: Record<string, string> = {
  feasibility: "Feasibility",
  budget_fit: "Budget fit",
  risk_coverage: "Risk coverage",
  coherence: "Coherence",
};

export function CritiqueHistoryList({ history, threshold }: CritiqueHistoryListProps) {
  return (
    <ul className="space-y-3">
      {history.map((note) => {
        const delta = note.score_delta;

        return (
          <li key={note.iteration} className="animate-fade-slide-in rounded-xl border border-ink-100 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold text-ink-800">Iteration {note.iteration}</span>
              <span className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-ink-500">
                  score <span className="font-medium text-ink-700">{note.score.toFixed(2)}</span>
                  <span className="text-ink-300"> / {threshold.toFixed(2)} to pass</span>
                </span>
                {delta !== null && Math.abs(delta) >= 0.005 && (
                  <span className={delta > 0 ? "font-medium text-budget-600" : "font-medium text-risk-600"}>
                    {delta > 0 ? "+" : ""}
                    {delta.toFixed(2)}
                  </span>
                )}
                {note.duration_ms !== null && (
                  <span className="text-xs text-ink-300">{formatDuration(note.duration_ms)}</span>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    note.passed ? "bg-budget-100 text-budget-600" : "bg-logistics-100 text-logistics-600"
                  }`}
                >
                  {note.passed ? "passed" : "revising"}
                </span>
              </span>
            </div>

            {!note.passed && note.revision_targets.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {note.revision_targets.map((target) => {
                  const theme = AGENT_THEME[target as SpecialistKey];
                  return (
                    <span
                      key={target}
                      className={`rounded-full px-2 py-0.5 text-xs capitalize ${theme ? `${theme.chipBg} ${theme.chipText}` : "bg-ink-100 text-ink-600"}`}
                    >
                      {theme?.label ?? target}
                    </span>
                  );
                })}
              </div>
            )}

            {Object.entries(note.notes).length > 0 && (
              <dl className="mt-3 space-y-2 border-t border-ink-50 pt-3">
                {Object.entries(note.notes).map(([dimension, text]) => (
                  <div key={dimension}>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-ink-300">
                      {DIMENSION_LABELS[dimension] ?? dimension.replace(/_/g, " ")}
                    </dt>
                    <dd className="mt-0.5 text-sm leading-relaxed text-ink-600">{text}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}
