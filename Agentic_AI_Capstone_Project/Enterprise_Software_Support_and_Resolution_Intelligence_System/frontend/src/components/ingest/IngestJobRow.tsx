import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { getIngestStatus } from "../../api/endpoints";

interface IngestJobRowProps {
  jobId: string;
  filename: string;
  onCompleted: () => void;
}

export function IngestJobRow({ jobId, filename, onCompleted }: IngestJobRowProps) {
  const { data } = useQuery({
    queryKey: ["ingest-status", jobId],
    queryFn: () => getIngestStatus(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1500;
    },
  });

  const status = data?.status ?? "pending";

  useEffect(() => {
    if (status === "completed") onCompleted();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-700">
      <span className="truncate text-slate-700 dark:text-slate-200">{filename}</span>
      <div className="flex shrink-0 items-center gap-1.5 text-xs">
        {status === "completed" && (
          <>
            <CheckCircle2 size={14} className="text-green-600" />
            <span className="text-slate-500 dark:text-slate-400">
              {data?.stats ? `${data.stats.assets_new} new asset${data.stats.assets_new === 1 ? "" : "s"}` : "Done"}
            </span>
          </>
        )}
        {status === "failed" && (
          <>
            <XCircle size={14} className="text-red-600" />
            <span className="text-red-600">Failed</span>
          </>
        )}
        {(status === "pending" || status === "processing") && (
          <>
            <Loader2 size={14} className="animate-spin text-brand-500" />
            <span className="capitalize text-slate-500 dark:text-slate-400">{status}</span>
          </>
        )}
      </div>
    </div>
  );
}
