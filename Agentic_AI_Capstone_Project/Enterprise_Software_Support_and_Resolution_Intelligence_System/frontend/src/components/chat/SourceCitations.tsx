import { useState } from "react";
import { FileText, Table2, Database, Workflow, ChevronDown } from "lucide-react";
import type { SourceRef, SourceType } from "../../api/types";

const ICONS: Record<SourceType, typeof FileText> = {
  chunk: FileText,
  table: Table2,
  sql: Database,
  diagram: Workflow,
};

function sourceKey(source: SourceRef): string {
  return source.type === "sql"
    ? `sql:${source.table}:${source.record_id}`
    : `${source.type}:${source.source_document}:${source.section_header}:${source.page_number}`;
}

/** Two retrieved chunks can legitimately share the exact same document/
 * section/page (e.g. adjacent chunks split from one paragraph) — shown
 * as one badge instead of visually-identical duplicates. */
function dedupeSources(sources: SourceRef[]): SourceRef[] {
  const seen = new Set<string>();
  return sources.filter((source) => {
    const key = sourceKey(source);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function SourceCitations({ sources }: { sources: SourceRef[] }) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (sources.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {dedupeSources(sources).map((source, index) => {
        const Icon = ICONS[source.type];
        const label =
          source.type === "sql"
            ? `${source.table ?? "record"}${source.record_id != null ? ` #${source.record_id}` : ""}`
            : (source.source_document ?? "Source");
        const isExpanded = expandedIndex === index;
        // Document name and section header can both be long enough to
        // truncate — a hover-only tooltip is invisible in practice (the
        // exact reason multiple citations used to look like meaningless
        // duplicates), so this is a real toggle instead: click to see the
        // full, untruncated document name/section header/page number.
        return (
          <button
            key={index}
            type="button"
            onClick={() => setExpandedIndex(isExpanded ? null : index)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            <Icon size={12} className="shrink-0" />
            <span className={isExpanded ? "" : "max-w-40 truncate"}>{label}</span>
            {source.section_header && (
              <span className={`text-slate-400 ${isExpanded ? "" : "max-w-35 truncate"}`}>
                — {source.section_header}
              </span>
            )}
            {source.page_number != null && <span className="shrink-0 text-slate-400">p.{source.page_number}</span>}
            <ChevronDown size={11} className={`shrink-0 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
          </button>
        );
      })}
    </div>
  );
}
