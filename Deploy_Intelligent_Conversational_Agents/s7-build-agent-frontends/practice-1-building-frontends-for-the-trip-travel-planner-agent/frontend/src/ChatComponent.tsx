// src/components/ChatComponent.tsx
import React, { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import ReactMarkdown from "react-markdown";
import { streamChatMessage } from "./apiService";
import "./styles.css";

interface Message {
  role: "user" | "assistant";
  content: string;
}

// Loading indicator component
const LoadingIndicator = () => (
  <div className="loading-indicator">
    <span>AI is processing</span>
    <div className="loading-dots">
      <div className="loading-dot"></div>
      <div className="loading-dot"></div>
      <div className="loading-dot"></div>
    </div>
  </div>
);

const ChatComponent: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize unique session
  useEffect(() => {
    setSessionId(uuidv4());
  }, []);

  // Auto-scroll when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    const assistantMessage: Message = { role: "assistant", content: "" };
    
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);

    // Task 1: Display streaming AI responses received from backend 
    // and handle errors gracefully.

    try {
      await streamChatMessage(input, sessionId, (chunk: string) => {
        setMessages((prev) => {
          const updated = [...prev];
          const assistantIndex = updated.length - 1;
          updated[assistantIndex] = {
            role: "assistant",
            content: updated[assistantIndex].content + chunk,
          };
          return updated;
        });
      });
    } catch (error) {
      console.error("Streaming error:", error);

      setMessages((prev) => {
        const updated = [...prev];
        const assistantIndex = updated.length - 1;
        updated[assistantIndex] = {
          role: "assistant",
          content: "Error: Failed to get response from server.",
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };



  return (
    <div className="chat-container">
      <h2 className="title">Trip & Travel Planner Chat</h2>

      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <strong>{msg.role === "user" ? "You: " : "Agent: "}</strong>
            {msg.role === "assistant" ? (
              <ReactMarkdown
                components={{
                  // Open links in new tab for better UX
                  a: ({ node, ...props }: any) => (
                    <a target="_blank" rel="noopener noreferrer" {...props} />
                  ),
                }}
              >
                {msg.content}
              </ReactMarkdown>
            ) : (
              msg.content
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
            <LoadingIndicator />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <input
          type="text"
          value={input}
          placeholder="Where would you like to go?"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          disabled={isLoading}
        />
        <button onClick={sendMessage} disabled={isLoading || !input.trim()}>
          {isLoading ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
};

export default ChatComponent;