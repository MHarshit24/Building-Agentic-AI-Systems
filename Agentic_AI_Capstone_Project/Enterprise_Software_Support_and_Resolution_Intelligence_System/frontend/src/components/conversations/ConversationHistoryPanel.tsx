import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { archiveConversation, listConversations, unarchiveConversation } from "../../api/endpoints";
import { ConversationListItem } from "./ConversationListItem";
import { Spinner } from "../ui/Spinner";

export function ConversationHistoryPanel() {
  const [showArchived, setShowArchived] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["conversations", showArchived],
    queryFn: () => listConversations({ include_archived: showArchived }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["conversations"] });
  const archiveMutation = useMutation({ mutationFn: archiveConversation, onSuccess: invalidate });
  const unarchiveMutation = useMutation({ mutationFn: unarchiveConversation, onSuccess: invalidate });
  const mutationPending = archiveMutation.isPending || unarchiveMutation.isPending;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 pb-1 pt-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Conversations</h2>
        <button
          type="button"
          onClick={() => setShowArchived((v) => !v)}
          className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
        >
          {showArchived ? "Hide archived" : "Show archived"}
        </button>
      </div>
      <div className="scroll-thin flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
        {isLoading && (
          <div className="flex justify-center py-4 text-slate-400">
            <Spinner />
          </div>
        )}
        {!isLoading && data?.conversations.length === 0 && (
          <p className="px-3 py-4 text-center text-sm text-slate-400">No conversations yet.</p>
        )}
        {data?.conversations.map((c) => (
          <ConversationListItem
            key={c.conversation_id}
            conversation={c}
            onArchive={(id) => archiveMutation.mutate(id)}
            onUnarchive={(id) => unarchiveMutation.mutate(id)}
            disabled={mutationPending}
          />
        ))}
      </div>
    </div>
  );
}
