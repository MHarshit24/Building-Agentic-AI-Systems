import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listCustomers } from "../../api/endpoints";
import type { CustomerSummary } from "../../api/types";

interface CustomerPickerProps {
  value: CustomerSummary | null;
  onChange: (customer: CustomerSummary | null) => void;
  disabled?: boolean;
}

// A proper searchable picker, not a blind "type a number" field — closes a
// real gap found via a user bug report ("why can't I send a query"): there
// was no way anywhere in the app to discover a valid customer_id, so the
// new-chat customer field was effectively unfillable. ~124 seeded customers
// (scripts/seed_synthetic_data.py) is fetched once and filtered client-side
// as the user types, since that's small enough to not need per-keystroke
// server round-trips.
export function CustomerPicker({ value, onChange, disabled }: CustomerPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["customers"], queryFn: () => listCustomers() });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    const pool = q ? data.customers.filter((c) => c.company_name.toLowerCase().includes(q)) : data.customers;
    // Was capped at 20 — real bug found via manual QA: the backend orders
    // customers alphabetically by company_name, so with ~124 seeded
    // customers (4 fixed starter companies + ~120 "Company_N" synthetic
    // rows sorted lexicographically between them), a starter company whose
    // name starts late in the alphabet (e.g. "Gamma Retail", "Delta
    // Logistics") never appeared in the unsearched default view at all —
    // only a name-matching search could surface it, which a new agent who
    // doesn't yet know the company exists has no way to type. 150 matches
    // GET /customers' own default page size (routes_customers.py), so this
    // covers the whole seeded set in the already-scrollable dropdown below.
    return pool.slice(0, 150);
  }, [data, query]);

  return (
    <div className="relative">
      <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Customer</label>
      <input
        type="text"
        disabled={disabled}
        value={value ? `${value.company_name} (#${value.customer_id})` : query}
        onChange={(e) => {
          if (value) onChange(null);
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={isLoading ? "Loading customers…" : "Search by company name…"}
        className="mt-1 w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm shadow-sm outline-none transition-all focus:border-brand-500 focus:shadow-md focus:ring-2 focus:ring-brand-500/40 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:disabled:bg-slate-900"
      />
      {open && !disabled && filtered.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
          {filtered.map((c) => (
            <li key={c.customer_id}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange(c);
                  setQuery("");
                  setOpen(false);
                }}
                className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
              >
                <span className="font-medium text-slate-800 dark:text-slate-100">{c.company_name}</span>
                <span className="text-xs text-slate-400">
                  #{c.customer_id} · {c.subscription_tier ?? "—"} · {c.region ?? "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
