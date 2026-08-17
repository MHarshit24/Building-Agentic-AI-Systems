import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listCustomers } from "../api/endpoints";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";

// Real gap found via manual QA: the chat composer's CustomerPicker is a
// type-ahead search box, not a browsable list — a new support agent who
// doesn't yet know which companies exist has no way to discover them there.
// This page is the actual browse surface: every seeded customer, one fetch,
// filtered client-side (same ~124-row scale CustomerPicker already assumes
// is small enough for that). Agent-visible, not admin-only — agents already
// have full customer read access via the picker today, so this adds
// discoverability, not a new permission boundary.
function statusTone(status: string | null): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "Active":
      return "success";
    case "Trial":
      return "warning";
    case "Suspended":
    case "Cancelled":
      return "danger";
    default:
      return "neutral";
  }
}

export default function CustomersPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["customers", "all"], queryFn: () => listCustomers() });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return data.customers;
    return data.customers.filter((c) => c.company_name.toLowerCase().includes(q));
  }, [data, search]);

  return (
    <div className="scroll-thin h-full overflow-y-auto bg-slate-50 px-8 py-6 dark:bg-slate-950">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">Customers</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {data ? `${data.total} customers on file.` : "Every customer available to look up in chat."}
          </p>
        </div>
        <Input
          placeholder="Filter by company name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64"
        />
      </div>

      {isLoading ? (
        <div className="mt-8 flex justify-center text-slate-400">
          <Spinner size={24} />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Company</th>
                <th className="px-4 py-2 font-medium">Customer ID</th>
                <th className="px-4 py-2 font-medium">Tier</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Region</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {filtered.map((c) => (
                <tr key={c.customer_id}>
                  <td className="px-4 py-2 font-medium text-slate-800 dark:text-slate-100">{c.company_name}</td>
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400">#{c.customer_id}</td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{c.subscription_tier ?? "—"}</td>
                  <td className="px-4 py-2">
                    <Badge tone={statusTone(c.account_status)}>{c.account_status ?? "Unknown"}</Badge>
                  </td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{c.region ?? "—"}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No customers match "{search}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
