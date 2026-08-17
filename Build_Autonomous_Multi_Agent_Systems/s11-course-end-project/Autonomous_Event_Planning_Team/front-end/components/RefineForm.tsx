"use client";

import { useState, type FormEvent } from "react";
import { AGENT_ORDER, AGENT_THEME } from "./agentTheme";
import { SpinnerIcon } from "./icons";
import type { SpecialistKey } from "../lib/types";

interface RefineFormProps {
  onSubmit: (instruction: string, targetAgents: string[] | null) => void;
  disabled?: boolean;
}

export function RefineForm({ onSubmit, disabled }: RefineFormProps) {
  const [instruction, setInstruction] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<Set<SpecialistKey>>(new Set());
  const [formError, setFormError] = useState<string | null>(null);

  function toggleAgent(key: SpecialistKey) {
    setSelectedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!instruction.trim()) {
      setFormError("Enter an instruction describing the revision.");
      return;
    }
    setFormError(null);
    onSubmit(instruction.trim(), selectedAgents.size > 0 ? Array.from(selectedAgents) : null);
    setInstruction("");
    setSelectedAgents(new Set());
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="animate-fade-in space-y-4 rounded-2xl border border-ink-100 bg-white p-6 shadow-sm sm:p-7"
    >
      <div>
        <h3 className="font-display text-base font-semibold text-ink-800">Refine this plan</h3>
        <p className="mt-1 text-sm text-ink-400">
          Describe a change and the relevant specialists will revise the plan.
        </p>
      </div>

      <textarea
        rows={2}
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="e.g. Reduce the catering budget and add a backup venue option"
        className="w-full rounded-lg border border-ink-100 bg-white px-3.5 py-2.5 text-sm text-ink-800 placeholder:text-ink-300 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
      />

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-300">
          Target specialists (optional — leave empty to let the reviewer decide)
        </p>
        <div className="flex flex-wrap gap-2">
          {AGENT_ORDER.map((key) => {
            const theme = AGENT_THEME[key];
            const Icon = theme.Icon;
            const selected = selectedAgents.has(key);
            return (
              <button
                key={key}
                type="button"
                onClick={() => toggleAgent(key)}
                aria-pressed={selected}
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                  selected
                    ? `${theme.border} ${theme.chipBg} ${theme.chipText}`
                    : "border-ink-100 text-ink-500 hover:border-ink-200 hover:bg-ink-50"
                }`}
              >
                <Icon className="h-4 w-4" />
                {theme.label}
              </button>
            );
          })}
        </div>
      </div>

      {formError && <p className="rounded-lg bg-risk-50 px-3.5 py-2 text-sm text-risk-600">{formError}</p>}

      <button
        type="submit"
        disabled={disabled}
        className="flex items-center gap-2 rounded-lg border border-brand-600 px-4 py-2 text-sm font-semibold text-brand-600 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled && <SpinnerIcon className="h-4 w-4" />}
        Submit revision
      </button>
    </form>
  );
}
