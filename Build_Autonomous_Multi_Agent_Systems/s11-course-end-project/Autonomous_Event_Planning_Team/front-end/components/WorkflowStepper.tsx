import { CheckCircleIcon, SpinnerIcon } from "./icons";

export type WorkflowStage = "planning" | "reviewing" | "complete";

const STAGE_ORDER: WorkflowStage[] = ["planning", "reviewing", "complete"];

// "Brief" is always shown as already complete — by the time this renders,
// the brief has already been submitted and polling has started.
const STEPS = [
  { label: "Brief" },
  { label: "Planning" },
  { label: "Reviewing" },
  { label: "Complete" },
];

interface WorkflowStepperProps {
  currentStage: WorkflowStage;
}

export function WorkflowStepper({ currentStage }: WorkflowStepperProps) {
  const currentIndex = 1 + STAGE_ORDER.indexOf(currentStage);

  return (
    <div className="flex items-start">
      {STEPS.map((step, index) => {
        const isLast = index === STEPS.length - 1;
        // The last step is only ever reached once the plan is truly
        // terminal (ProgressPanel never reports "complete" — only
        // BlueprintView does, once a plan has a final blueprint), so treat
        // it as done rather than perpetually "active"/spinning.
        const isDone = index < currentIndex || (isLast && currentStage === "complete");
        const isActive = index === currentIndex && !isDone;

        return (
          <div key={step.label} className={`flex items-start ${isLast ? "" : "flex-1"}`}>
            <div className="flex flex-col items-center">
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-500 ${
                  isDone
                    ? "border-brand-600 bg-brand-600 text-white"
                    : isActive
                      ? "border-brand-600 bg-brand-50 text-brand-600"
                      : "border-ink-200 bg-white text-ink-300"
                }`}
              >
                {isDone ? (
                  <CheckCircleIcon className="h-5 w-5 animate-pop-in" />
                ) : isActive ? (
                  <SpinnerIcon className="h-4 w-4" />
                ) : (
                  <span className="text-xs font-medium">{index + 1}</span>
                )}
              </div>
              <span
                className={`mt-1.5 text-center text-xs font-medium transition-colors duration-500 ${
                  isDone || isActive ? "text-ink-800" : "text-ink-300"
                }`}
              >
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div className="mx-2 mt-4 h-0.5 flex-1 overflow-hidden rounded bg-ink-100">
                <div
                  className="h-full bg-brand-600 transition-all duration-700 ease-out"
                  style={{ width: index < currentIndex ? "100%" : "0%" }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
