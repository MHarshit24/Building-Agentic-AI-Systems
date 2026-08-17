import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Send, Info } from "lucide-react";
import { Button } from "../ui/Button";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  /** Set when sending is blocked for a reason OTHER than "already
   * streaming" (e.g. no customer selected yet) — shown as a visible hint
   * instead of the button just silently doing nothing, which is exactly
   * the confusing behavior a real user hit ("why can't I send a query"). */
  blockedReason?: string;
}

export function ChatInput({ onSend, disabled, blockedReason }: ChatInputProps) {
  const [value, setValue] = useState("");
  const isBlocked = disabled || !!blockedReason;

  const send = () => {
    const trimmed = value.trim();
    if (!trimmed || isBlocked) return;
    onSend(trimmed);
    setValue("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    send();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
      {blockedReason && (
        <div className="flex items-center gap-1.5 px-3 pt-2 text-xs text-amber-600 dark:text-amber-400">
          <Info size={13} className="shrink-0" />
          {blockedReason}
        </div>
      )}
      <form onSubmit={handleSubmit} className="flex items-end gap-2 p-3">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder="Describe the issue…"
          className="max-h-32 flex-1 resize-none rounded-lg border border-slate-200 px-3.5 py-2.5 text-sm shadow-sm outline-none transition-all focus:border-brand-500 focus:shadow-md focus:ring-2 focus:ring-brand-500/40 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:disabled:bg-slate-900"
        />
        <Button type="submit" disabled={isBlocked || !value.trim()} aria-label="Send message">
          <Send size={16} />
        </Button>
      </form>
    </div>
  );
}
