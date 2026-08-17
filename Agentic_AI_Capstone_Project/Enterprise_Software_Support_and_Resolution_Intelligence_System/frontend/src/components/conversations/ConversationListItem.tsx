import { NavLink } from "react-router-dom";
import { Archive, ArchiveRestore, AlertTriangle } from "lucide-react";
import type { ConversationSummary } from "../../api/types";
import { Badge } from "../ui/Badge";
import { toneForConversationStatus } from "../../lib/badgeTones";

interface ConversationListItemProps {
  conversation: ConversationSummary;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
  disabled: boolean;
}

export function ConversationListItem({ conversation, onArchive, onUnarchive, disabled }: ConversationListItemProps) {
  const isArchived = conversation.status === "archived";

  return (
    <div className="group relative">
      <NavLink
        to={`/chat/${conversation.conversation_id}`}
        className={({ isActive }) =>
          `block rounded-lg px-3 py-2 pr-8 text-sm transition-colors ${
            isActive
              ? "bg-brand-50 text-brand-900 dark:bg-brand-900/30 dark:text-brand-200"
              : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          }`
        }
      >
        <div className="flex items-center gap-1.5">
          {conversation.escalated && (
            <AlertTriangle size={12} className="shrink-0 text-purple-600 dark:text-purple-400" />
          )}
          <span className="truncate font-medium">Customer #{conversation.customer_id}</span>
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          <Badge tone={toneForConversationStatus(conversation.status)}>{conversation.status}</Badge>
          <span className="text-xs text-slate-400">
            {new Date(conversation.last_message_at).toLocaleDateString()}
          </span>
        </div>
      </NavLink>
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          isArchived ? onUnarchive(conversation.conversation_id) : onArchive(conversation.conversation_id)
        }
        className="absolute right-1.5 top-2 hidden rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700 group-hover:block disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"
        title={isArchived ? "Unarchive" : "Archive"}
      >
        {isArchived ? <ArchiveRestore size={14} /> : <Archive size={14} />}
      </button>
    </div>
  );
}
