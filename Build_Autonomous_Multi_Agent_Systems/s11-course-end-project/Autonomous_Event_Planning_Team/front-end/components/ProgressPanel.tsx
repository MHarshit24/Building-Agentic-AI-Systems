import { PROVIDER_LABELS, type PlanResponse } from "../lib/types";
import { AgentGraph } from "./AgentGraph";
import { CritiqueHistoryList } from "./CritiqueHistoryList";
import { SparkleIcon } from "./icons";
import { WorkflowStepper } from "./WorkflowStepper";

interface ProgressPanelProps {
  plan: PlanResponse;
}

export function ProgressPanel({ plan }: ProgressPanelProps) {
  const readyCount = plan.specialist_outputs_ready.length;
  const stage = readyCount < 5 ? "planning" : "reviewing";

  const specialistFraction = Math.min(readyCount / 5, 1);
  const iterationFraction = plan.max_iterations
    ? Math.min(plan.iteration_count / plan.max_iterations, 1)
    : 0;
  const overallProgress = Math.round(((iterationFraction + specialistFraction) / 2) * 100);

  return (
    <div className="animate-fade-in space-y-6 rounded-2xl border border-ink-100 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
            <SparkleIcon className="h-5 w-5 animate-float" />
          </span>
          <div>
            <h2 className="font-display text-lg font-semibold text-ink-800">Your team is at work</h2>
            <p className="text-sm text-ink-400">
              Iteration {Math.max(plan.iteration_count, 1)}
              {plan.max_iterations ? ` of ${plan.max_iterations}` : ""}
              {plan.provider && ` · ${PROVIDER_LABELS[plan.provider]}`}
            </p>
          </div>
        </div>
        <div className="w-full max-w-[180px] sm:w-40">
          <div className="mb-1 flex items-center justify-between text-xs text-ink-400">
            <span>Progress</span>
            <span className="font-medium text-ink-600">{overallProgress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-400 to-marketing-500 transition-all duration-700 ease-out"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>
      </div>

      <WorkflowStepper currentStage={stage} />

      <div className="rounded-xl border border-ink-100 bg-paper/60 p-2 sm:p-4">
        <AgentGraph plan={plan} />
      </div>

      {plan.critique_history.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-ink-700">Review history</h3>
          <CritiqueHistoryList history={plan.critique_history} threshold={plan.quality_gate_threshold} />
        </div>
      )}
    </div>
  );
}
