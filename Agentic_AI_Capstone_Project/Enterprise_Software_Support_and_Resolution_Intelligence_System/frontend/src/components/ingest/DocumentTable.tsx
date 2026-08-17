import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { deleteDocument, listDocuments } from "../../api/endpoints";
import { Spinner } from "../ui/Spinner";

export function DocumentTable() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["documents"], queryFn: listDocuments });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8 text-slate-400">
        <Spinner />
      </div>
    );
  }

  if (!data || data.documents.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-400">No documents ingested yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          <tr>
            <th className="px-4 py-2 font-medium">Document</th>
            <th className="px-4 py-2 font-medium">Category</th>
            <th className="px-4 py-2 font-medium">Version</th>
            <th className="px-4 py-2 font-medium">Active assets</th>
            <th className="px-4 py-2 font-medium">Ingested</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
          {data.documents.map((doc) => (
            <tr key={doc.document_id}>
              <td className="px-4 py-2 font-medium text-slate-800 dark:text-slate-100">
                {doc.doc_title ?? doc.document_id}
              </td>
              <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{doc.category ?? "—"}</td>
              <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{doc.product_version ?? "—"}</td>
              <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{doc.active_asset_count}</td>
              <td className="px-4 py-2 text-slate-500 dark:text-slate-400">
                {new Date(doc.ingested_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-2 text-right">
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(doc.document_id)}
                  disabled={deleteMutation.isPending}
                  className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20"
                  title="Delete document"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
