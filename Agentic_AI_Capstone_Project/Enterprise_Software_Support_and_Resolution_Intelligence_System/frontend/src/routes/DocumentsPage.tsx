import { IngestPanel } from "../components/ingest/IngestPanel";
import { DocumentTable } from "../components/ingest/DocumentTable";

export default function DocumentsPage() {
  return (
    <div className="scroll-thin h-full overflow-y-auto bg-slate-50 px-8 py-6 dark:bg-slate-950">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">Documents</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Ingest and manage the knowledge base the RAG pipeline retrieves from.
      </p>

      <div className="mt-6">
        <IngestPanel />
      </div>

      <div className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Ingested documents</h2>
        <DocumentTable />
      </div>
    </div>
  );
}
