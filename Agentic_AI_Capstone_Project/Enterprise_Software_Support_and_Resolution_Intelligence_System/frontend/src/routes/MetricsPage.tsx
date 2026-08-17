import { useQuery } from "@tanstack/react-query";
import { getMetrics } from "../api/endpoints";
import { Spinner } from "../components/ui/Spinner";

interface StatTileProps {
  label: string;
  value: string | null;
  suffix?: string;
}

function StatTile({ label, value, suffix }: StatTileProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 bg-gradient-brand bg-clip-text text-2xl font-semibold text-transparent">
        {value == null ? "—" : `${value}${suffix ?? ""}`}
      </p>
    </div>
  );
}

function pct(value: number | null): string | null {
  return value == null ? null : (value * 100).toFixed(0);
}

export default function MetricsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["metrics"], queryFn: getMetrics });

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        <Spinner size={24} />
      </div>
    );
  }

  return (
    <div className="scroll-thin h-full overflow-y-auto bg-slate-50 px-8 py-6 dark:bg-slate-950">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">SLO Metrics</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Window: {new Date(data.window.from).toLocaleDateString()} – {new Date(data.window.to).toLocaleDateString()}
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <StatTile label="P50 latency" value={data.latency_ms.p50 != null ? `${data.latency_ms.p50}` : null} suffix="ms" />
        <StatTile label="P95 latency" value={data.latency_ms.p95 != null ? `${data.latency_ms.p95}` : null} suffix="ms" />
        <StatTile
          label="Cost / ticket"
          value={data.cost_per_ticket_usd != null ? `$${data.cost_per_ticket_usd.toFixed(3)}` : null}
        />
        <StatTile label="Escalation rate" value={pct(data.escalation_rate)} suffix="%" />
        <StatTile label="Task success rate" value={pct(data.task_success_rate)} suffix="%" />
        <StatTile label="SQL correctness" value={pct(data.sql_correctness)} suffix="%" />
        <StatTile label="Routing accuracy" value={pct(data.query_routing_accuracy)} suffix="%" />
        <StatTile label="Risk classification accuracy" value={pct(data.risk_classification_accuracy)} suffix="%" />
        <StatTile label="Escalation recall" value={pct(data.escalation_recall)} suffix="%" />
        <StatTile label="Faithfulness" value={pct(data.faithfulness)} suffix="%" />
        <StatTile label="Answer relevance" value={pct(data.answer_relevance)} suffix="%" />
        <StatTile label="Context precision" value={pct(data.context_precision)} suffix="%" />
        <StatTile label="Context recall" value={pct(data.context_recall)} suffix="%" />
      </div>

      {data.last_eval_run_at && (
        <p className="mt-6 text-xs text-slate-400">
          Last golden-eval run: {new Date(data.last_eval_run_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
