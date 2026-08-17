"use client";

import { motion, type Variants } from "framer-motion";
import { useEffect, useState, type FormEvent } from "react";
import { getHealth } from "../lib/api";
import {
  PROVIDER_LABELS,
  PROVIDERS,
  QUALITY_GATE_THRESHOLD_MAX,
  QUALITY_GATE_THRESHOLD_MIN,
  QUALITY_GATE_THRESHOLD_STEP,
  type EventBrief,
  type Provider,
} from "../lib/types";
import { CloseIcon, SparkleIcon, SpinnerIcon } from "./icons";

interface BriefFormProps {
  onSubmit: (brief: EventBrief) => void;
  disabled?: boolean;
}

const inputClass =
  "w-full rounded-lg border border-ink-100 bg-white px-3.5 py-2.5 text-sm text-ink-800 placeholder:text-ink-300 transition-shadow focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100";

const labelClass = "mb-1.5 block text-sm font-medium text-ink-600";

const fieldVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.04, duration: 0.35, ease: "easeOut" } }),
};

export function BriefForm({ onSubmit, disabled }: BriefFormProps) {
  const [eventType, setEventType] = useState("");
  const [objective, setObjective] = useState("");
  const [audienceSize, setAudienceSize] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [maxAmount, setMaxAmount] = useState("");
  const [preferredDate, setPreferredDate] = useState("");
  const [durationDays, setDurationDays] = useState("1");
  const [venuePreference, setVenuePreference] = useState("");
  const [constraints, setConstraints] = useState<string[]>([]);
  const [constraintDraft, setConstraintDraft] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Only offer providers with real credentials configured on the backend
  // (see GET /health -> available_providers); null while that first check
  // is in flight. Azure OpenAI is the default whenever it's available.
  const [availableProviders, setAvailableProviders] = useState<Provider[] | null>(null);
  const [provider, setProvider] = useState<Provider | null>(null);

  // The quality gate's pass bar (see ReflectionAgent.critique). Initialized
  // from GET /health's default_quality_gate_threshold once it loads, rather
  // than hardcoding a guess that could drift from the server's actual
  // config default.
  const [qualityGateThreshold, setQualityGateThreshold] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (cancelled) return;
        setAvailableProviders(health.available_providers);
        setProvider(
          health.available_providers.includes("azure") ? "azure" : (health.available_providers[0] ?? null)
        );
        setQualityGateThreshold(health.default_quality_gate_threshold);
      })
      .catch(() => {
        if (cancelled) return;
        setAvailableProviders([]);
        setQualityGateThreshold(QUALITY_GATE_THRESHOLD_MIN);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function addConstraint() {
    const trimmed = constraintDraft.trim();
    if (!trimmed) return;
    setConstraints((prev) => [...prev, trimmed]);
    setConstraintDraft("");
  }

  function removeConstraint(index: number) {
    setConstraints((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const audienceSizeNumber = Number(audienceSize);
    const maxAmountNumber = Number(maxAmount);
    const durationDaysNumber = Number(durationDays);

    if (!eventType.trim() || !objective.trim() || !preferredDate) {
      setFormError("Event type, objective, and preferred date are required.");
      return;
    }
    if (!Number.isFinite(audienceSizeNumber) || audienceSizeNumber <= 0) {
      setFormError("Audience size must be a positive number.");
      return;
    }
    if (!Number.isFinite(maxAmountNumber) || maxAmountNumber <= 0) {
      setFormError("Budget limit must be a positive number.");
      return;
    }
    if (!Number.isFinite(durationDaysNumber) || durationDaysNumber < 1) {
      setFormError("Duration must be at least 1 day.");
      return;
    }

    setFormError(null);
    onSubmit({
      event_type: eventType.trim(),
      objective: objective.trim(),
      audience_size: audienceSizeNumber,
      budget: { currency: currency.trim() || "USD", max_amount: maxAmountNumber },
      timeline: { preferred_date: preferredDate, duration_days: durationDaysNumber },
      venue_preference: venuePreference.trim() || null,
      constraints,
      provider,
      quality_gate_threshold: qualityGateThreshold,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="animate-fade-in space-y-7 rounded-2xl border border-ink-100 bg-white p-6 shadow-sm sm:p-8"
    >
      <div>
        <h2 className="font-display text-xl font-semibold text-ink-800">Tell us about your event</h2>
        <p className="mt-1 text-sm text-ink-400">
          A crew of specialist agents — logistics, budget, marketing, schedule, and risk — will turn this into a full,
          reviewed blueprint.
        </p>
      </div>

      {availableProviders === null ? (
        <div className="h-20 w-full animate-shimmer rounded-lg bg-gradient-to-r from-ink-50 via-ink-100 to-ink-50 bg-[length:200%_100%]" />
      ) : (
        <motion.div variants={fieldVariants} custom={0} initial="hidden" animate="show" className="space-y-5">
          {availableProviders.length > 0 ? (
            <div>
              <label className={labelClass}>Model</label>
              <div className="flex flex-wrap gap-2">
                {PROVIDERS.filter((p) => availableProviders.includes(p)).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setProvider(p)}
                    aria-pressed={provider === p}
                    className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                      provider === p
                        ? "border-brand-300 bg-brand-50 text-brand-700"
                        : "border-ink-100 text-ink-500 hover:border-ink-200 hover:bg-ink-50"
                    }`}
                  >
                    {PROVIDER_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="rounded-lg bg-risk-50 px-3.5 py-2 text-sm text-risk-600">
              No LLM provider is configured on this backend yet.
            </p>
          )}

          {qualityGateThreshold !== null && (
            <div>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label className={labelClass} htmlFor="quality_gate_threshold">
                  Quality bar
                </label>
                <span className="font-display text-sm font-semibold text-brand-600">
                  {qualityGateThreshold.toFixed(2)}
                </span>
              </div>
              <input
                id="quality_gate_threshold"
                type="range"
                min={QUALITY_GATE_THRESHOLD_MIN}
                max={QUALITY_GATE_THRESHOLD_MAX}
                step={QUALITY_GATE_THRESHOLD_STEP}
                value={qualityGateThreshold}
                onChange={(e) => setQualityGateThreshold(Number(e.target.value))}
                className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-600"
              />
              <div className="mt-1 flex justify-between text-xs text-ink-300">
                <span>Lenient — fewer revisions</span>
                <span>Strict — more scrutiny</span>
              </div>
            </div>
          )}
        </motion.div>
      )}

      <motion.div variants={fieldVariants} custom={1} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="event_type">
            Event type
          </label>
          <input
            id="event_type"
            className={inputClass}
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            placeholder="Conference, product launch, workshop..."
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="audience_size">
            Audience size
          </label>
          <input
            id="audience_size"
            type="number"
            min={1}
            className={inputClass}
            value={audienceSize}
            onChange={(e) => setAudienceSize(e.target.value)}
            placeholder="150"
          />
        </div>
      </motion.div>

      <motion.div variants={fieldVariants} custom={2} initial="hidden" animate="show">
        <label className={labelClass} htmlFor="objective">
          Objective
        </label>
        <textarea
          id="objective"
          className={inputClass}
          rows={2}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="What is this event meant to achieve?"
        />
      </motion.div>

      <motion.div variants={fieldVariants} custom={3} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className={labelClass} htmlFor="currency">
            Currency
          </label>
          <input
            id="currency"
            className={inputClass}
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            placeholder="USD"
            maxLength={3}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="max_amount">
            Budget limit
          </label>
          <input
            id="max_amount"
            type="number"
            min={0}
            className={inputClass}
            value={maxAmount}
            onChange={(e) => setMaxAmount(e.target.value)}
            placeholder="80000"
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="duration_days">
            Duration (days)
          </label>
          <input
            id="duration_days"
            type="number"
            min={1}
            className={inputClass}
            value={durationDays}
            onChange={(e) => setDurationDays(e.target.value)}
          />
        </div>
      </motion.div>

      <motion.div variants={fieldVariants} custom={4} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="preferred_date">
            Preferred date
          </label>
          <input
            id="preferred_date"
            type="date"
            className={inputClass}
            value={preferredDate}
            onChange={(e) => setPreferredDate(e.target.value)}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="venue_preference">
            Venue preference (optional)
          </label>
          <input
            id="venue_preference"
            className={inputClass}
            value={venuePreference}
            onChange={(e) => setVenuePreference(e.target.value)}
            placeholder="Downtown hotel ballroom"
          />
        </div>
      </motion.div>

      <motion.div variants={fieldVariants} custom={5} initial="hidden" animate="show">
        <label className={labelClass} htmlFor="constraint_draft">
          Constraints
        </label>
        <div className="flex gap-2">
          <input
            id="constraint_draft"
            className={inputClass}
            value={constraintDraft}
            onChange={(e) => setConstraintDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addConstraint();
              }
            }}
            placeholder="e.g. Must include a live product demo"
          />
          <button
            type="button"
            onClick={addConstraint}
            className="shrink-0 rounded-lg border border-ink-200 px-3.5 py-2 text-sm font-medium text-ink-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600"
          >
            Add
          </button>
        </div>
        {constraints.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {constraints.map((constraint, index) => (
              <li
                key={`${constraint}-${index}`}
                className="animate-pop-in flex items-center gap-1.5 rounded-full bg-brand-50 py-1.5 pl-3 pr-2 text-sm text-brand-700"
              >
                <span>{constraint}</span>
                <button
                  type="button"
                  onClick={() => removeConstraint(index)}
                  className="rounded-full p-0.5 text-brand-400 transition-colors hover:bg-brand-100 hover:text-brand-600"
                  aria-label={`Remove constraint: ${constraint}`}
                >
                  <CloseIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </motion.div>

      {formError && (
        <p className="rounded-lg bg-risk-50 px-3.5 py-2 text-sm text-risk-600">{formError}</p>
      )}

      <button
        type="submit"
        disabled={disabled || availableProviders?.length === 0}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-marketing-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto sm:px-6"
      >
        {disabled ? (
          <>
            <SpinnerIcon className="h-4 w-4" /> Assembling your crew...
          </>
        ) : (
          <>
            <SparkleIcon className="h-4 w-4" /> Generate plan
          </>
        )}
      </button>
    </form>
  );
}
