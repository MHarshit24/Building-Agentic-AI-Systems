import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";
import { PROVIDER_LABELS, type CritiqueNote, type EventBlueprint, type Provider, type SpecialistKey } from "../lib/types";
import { AGENT_THEME, type AgentKey } from "./agentTheme";
import { CritiqueHistoryList } from "./CritiqueHistoryList";
import { SparkleIcon } from "./icons";
import { StatusBadge } from "./StatusBadge";
import { WorkflowStepper } from "./WorkflowStepper";

interface BlueprintViewProps {
  blueprint: EventBlueprint;
  status: string;
  critiqueHistory: CritiqueNote[];
  qualityGateThreshold: number;
  provider: Provider | null;
}

const sectionVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.4, ease: "easeOut" } }),
};

export function BlueprintView({ blueprint, status, critiqueHistory, qualityGateThreshold, provider }: BlueprintViewProps) {
  const categoryAmounts = Object.values(blueprint.budget.category_breakdown);
  const maxCategoryAmount = categoryAmounts.length > 0 ? Math.max(...categoryAmounts) : 1;

  return (
    <div className="space-y-5">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="overflow-hidden rounded-2xl border border-ink-100 bg-white shadow-sm"
      >
        <div className="h-1.5 bg-gradient-to-r from-brand-500 via-marketing-500 to-schedule-500" />
        <div className="p-6 sm:p-8">
          <WorkflowStepper currentStage="complete" />
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-manager-100 text-manager-600">
                <SparkleIcon className="h-5 w-5" />
              </span>
              <h2 className="font-display text-xl font-semibold text-ink-800">Event blueprint</h2>
            </div>
            <div className="flex items-center gap-2">
              {provider && (
                <span className="rounded-full bg-ink-50 px-2.5 py-1 text-xs font-medium text-ink-500">
                  {PROVIDER_LABELS[provider]}
                </span>
              )}
              <StatusBadge status={status} />
            </div>
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-ink-600">{blueprint.overview.summary}</p>
          <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-ink-50 pt-5 sm:grid-cols-4 lg:grid-cols-6">
            <Field label="Event type" value={blueprint.overview.event_type} />
            <Field label="Audience" value={blueprint.overview.audience_size} />
            <Field label="Date" value={blueprint.overview.date} />
            <Field label="Objective" value={blueprint.overview.objective} />
          </dl>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section index={0} agentKey="logistics" title="Logistics">
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Venue" value={blueprint.logistics.venue} />
            <Field label="Capacity" value={blueprint.logistics.capacity} />
            <Field label="Layout" value={blueprint.logistics.layout_notes} />
            <Field label="Catering" value={blueprint.logistics.catering} />
          </dl>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-300">Vendors</dt>
              <dd className="mt-1.5">
                <TagList items={blueprint.logistics.vendors} agentKey="logistics" />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-300">Equipment</dt>
              <dd className="mt-1.5">
                <TagList items={blueprint.logistics.equipment} agentKey="logistics" />
              </dd>
            </div>
          </div>
        </Section>

        <Section index={1} agentKey="budget" title="Budget">
          <div className="mb-4 flex items-center justify-between gap-4">
            <Field
              label="Total estimated cost"
              value={`${blueprint.budget.total_estimated_cost.toLocaleString()} ${blueprint.budget.currency}`}
            />
            <span
              className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
                blueprint.budget.within_budget ? "bg-budget-100 text-budget-600" : "bg-risk-100 text-risk-600"
              }`}
            >
              {blueprint.budget.within_budget ? "Within budget" : "Over budget"}
            </span>
          </div>
          <div className="space-y-2.5">
            {Object.entries(blueprint.budget.category_breakdown).map(([category, amount]) => (
              <div key={category}>
                <div className="mb-1 flex justify-between text-xs text-ink-400">
                  <span className="capitalize">{category}</span>
                  <span>
                    {amount.toLocaleString()} {blueprint.budget.currency}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-ink-50">
                  <div
                    className="h-1.5 rounded-full bg-budget-500 transition-all duration-700 ease-out"
                    style={{ width: `${(amount / maxCategoryAmount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section index={2} agentKey="marketing" title="Marketing">
          <div className="mb-4">
            <dt className="text-xs font-semibold uppercase tracking-wide text-ink-300">Channels</dt>
            <dd className="mt-1.5">
              <TagList items={blueprint.marketing.channels} agentKey="marketing" />
            </dd>
          </div>
          <Field label="Outreach start" value={blueprint.marketing.outreach_start_date} />
          <div className="mt-4">
            <dt className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-300">Content calendar</dt>
            <ol className="space-y-1.5">
              {blueprint.marketing.content_calendar.map((item, index) => (
                <li key={index} className="flex gap-2 text-sm text-ink-600">
                  <span className="text-marketing-500">•</span>
                  {item}
                </li>
              ))}
            </ol>
          </div>
        </Section>

        <Section index={3} agentKey="schedule" title="Schedule">
          {blueprint.schedule.conflicts_detected.length > 0 && (
            <div className="mb-4 rounded-lg border border-logistics-200 bg-logistics-50 p-3 text-sm text-logistics-600">
              <p className="font-medium">Conflicts detected</p>
              <ul className="mt-1 list-inside list-disc">
                {blueprint.schedule.conflicts_detected.map((conflict, index) => (
                  <li key={index}>{conflict}</li>
                ))}
              </ul>
            </div>
          )}
          <ol className="space-y-2.5 border-l-2 border-schedule-200 pl-4">
            {blueprint.schedule.milestones.map((milestone, index) => (
              <li key={index} className="relative text-sm">
                <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-schedule-500" />
                <span className="font-medium text-ink-800">{milestone.date}</span>
                <span className="text-ink-400"> — {milestone.name}</span>
              </li>
            ))}
          </ol>
        </Section>

        <Section index={4} agentKey="risk" title="Risks" className="lg:col-span-2">
          {blueprint.risks.risks.length === 0 ? (
            <p className="text-sm text-ink-300">No risks identified.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-300">
                    <th className="pb-2 pr-4 font-semibold">Risk</th>
                    <th className="pb-2 pr-4 font-semibold">Likelihood</th>
                    <th className="pb-2 pr-4 font-semibold">Impact</th>
                    <th className="pb-2 font-semibold">Mitigation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-50">
                  {blueprint.risks.risks.map((risk, index) => (
                    <tr key={index}>
                      <td className="py-2.5 pr-4 font-medium text-ink-800">{risk.name}</td>
                      <td className="py-2.5 pr-4">
                        <RiskLevelBadge level={risk.likelihood} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <RiskLevelBadge level={risk.impact} />
                      </td>
                      <td className="py-2.5 text-ink-600">{risk.mitigation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {blueprint.risks.contingency_notes && (
            <p className="mt-4 rounded-lg bg-risk-50 p-3 text-sm text-ink-700">
              <span className="font-semibold text-risk-600">Contingency: </span>
              {blueprint.risks.contingency_notes}
            </p>
          )}
        </Section>
      </div>

      {critiqueHistory.length > 0 && (
        <Section index={5} agentKey="manager" title="Review history">
          <CritiqueHistoryList history={critiqueHistory} threshold={qualityGateThreshold} />
        </Section>
      )}
    </div>
  );
}

function Section({
  index,
  agentKey,
  title,
  children,
  className = "",
}: {
  index: number;
  agentKey: AgentKey;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const theme = AGENT_THEME[agentKey];
  const Icon = theme.Icon;
  return (
    <motion.div
      custom={index}
      variants={sectionVariants}
      initial="hidden"
      animate="show"
      className={`rounded-2xl border border-ink-100 bg-white p-6 shadow-sm sm:p-7 ${className}`}
    >
      <div className="mb-4 flex items-center gap-2.5">
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${theme.chipBg} ${theme.chipText}`}>
          <Icon className="h-4 w-4" />
        </span>
        <h3 className="font-display text-base font-semibold text-ink-800">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-300">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink-800">{value}</dd>
    </div>
  );
}

function TagList({ items, agentKey }: { items: string[]; agentKey: SpecialistKey }) {
  const theme = AGENT_THEME[agentKey];
  if (items.length === 0) return <span className="text-sm text-ink-300">None</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={`rounded-full px-2.5 py-0.5 text-xs ${theme.chipBg} ${theme.chipText}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function RiskLevelBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    low: "bg-budget-100 text-budget-600",
    medium: "bg-logistics-100 text-logistics-600",
    high: "bg-risk-100 text-risk-600",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${styles[level] ?? "bg-ink-100 text-ink-600"}`}
    >
      {level}
    </span>
  );
}
