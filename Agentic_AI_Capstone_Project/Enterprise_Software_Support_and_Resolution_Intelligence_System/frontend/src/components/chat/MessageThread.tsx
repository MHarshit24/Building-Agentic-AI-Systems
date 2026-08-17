import { useEffect, useRef } from "react";
import { MessageBubble, type ChatMessageVM } from "./MessageBubble";
import { Spinner } from "../ui/Spinner";

interface MessageThreadProps {
  messages: ChatMessageVM[];
}

export function MessageThread({ messages }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="scroll-thin flex-1 space-y-4 overflow-y-auto px-6 py-4">
      {messages.length === 0 && (
        <div className="flex h-full items-center justify-center text-sm text-slate-400">
          Ask a question to start a new conversation.
        </div>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message}>
          {message.pending && (
            <span className="inline-flex items-center gap-2 text-slate-400">
              <Spinner size={14} /> Thinking…
            </span>
          )}
        </MessageBubble>
      ))}
      {/* Only rendered once there's real content — otherwise space-y-4 still
          adds its margin above this empty sentinel, pushing total height
          just past the container's 100% and triggering a scrollbar for a
          thread that has nothing to scroll. */}
      {messages.length > 0 && <div ref={bottomRef} />}
    </div>
  );
}
