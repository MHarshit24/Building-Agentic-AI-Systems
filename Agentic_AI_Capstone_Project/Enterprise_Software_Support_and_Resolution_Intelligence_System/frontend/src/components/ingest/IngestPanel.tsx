import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { ingestDocument } from "../../api/endpoints";
import { IngestJobRow } from "./IngestJobRow";

interface TrackedJob {
  jobId: string;
  filename: string;
}

export function IngestPanel() {
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: (file: File) => ingestDocument(file, { doc_title: file.name }),
  });

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setUploadError(null);
    // POST /ingest accepts exactly one file per call — multi-file selection
    // is a frontend-orchestrated loop of individual uploads, not a single
    // multi-file request the backend doesn't support.
    for (const file of Array.from(fileList)) {
      try {
        const res = await uploadMutation.mutateAsync(file);
        setJobs((prev) => [{ jobId: res.job_id, filename: file.name }, ...prev]);
      } catch {
        setUploadError(`Failed to start ingestion for "${file.name}".`);
      }
    }
  }

  return (
    <div className="space-y-3">
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 py-8 text-center transition-colors hover:border-brand-400 hover:bg-brand-50/40 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-brand-950/20">
        <div className="bg-gradient-brand-soft flex h-10 w-10 items-center justify-center rounded-full">
          <Upload size={18} className="text-brand-600 dark:text-brand-400" />
        </div>
        <span className="text-sm text-slate-600 dark:text-slate-300">Click to upload one or more documents (PDF)</span>
        <input type="file" accept=".pdf" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />
      </label>

      {uploadError && <p className="text-sm text-red-600 dark:text-red-400">{uploadError}</p>}

      {jobs.length > 0 && (
        <div className="space-y-1.5">
          {jobs.map((job) => (
            <IngestJobRow
              key={job.jobId}
              jobId={job.jobId}
              filename={job.filename}
              onCompleted={() => queryClient.invalidateQueries({ queryKey: ["documents"] })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
