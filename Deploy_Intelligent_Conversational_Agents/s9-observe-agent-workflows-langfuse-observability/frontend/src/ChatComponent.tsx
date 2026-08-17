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

interface ChatComponentProps {
  getAccessTokenSilently: () => Promise<string>;
}

const ChatComponent: React.FC<ChatComponentProps> = ({ getAccessTokenSilently }) => {
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
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Add a placeholder assistant message for streaming updates
    const assistantIndex = messages.length + 1;
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      // Get JWT token for authentication
      const token = await getAccessTokenSilently();
      
      await streamChatMessage(input, sessionId, token, (chunk) => {
        // Skip if chunk is "done" or "[done]"
        const normalizedChunk = chunk.toLowerCase().replace(/[\[\]]/g, '');
        if (normalizedChunk === 'done') return;
        
        setMessages((prev) => {
          const updated = [...prev];
          const assistantMsg = updated[assistantIndex] || { role: "assistant", content: "" };
          assistantMsg.content += chunk;
          updated[assistantIndex] = assistantMsg;
          return updated;
        });
      });
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "⚠️ Something went wrong while streaming the response.",
        },
      ]);
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
