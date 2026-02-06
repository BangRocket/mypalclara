import { useEffect, useRef, useState } from "react";
import { Send, StopCircle } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";
import { MessageBubble } from "./MessageBubble";
import { FileUpload, type PendingFile } from "./FileUpload";

export function ChatView() {
  const messages = useChatStore((s) => s.messages);
  const connected = useChatStore((s) => s.connected);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const cancel = useChatStore((s) => s.cancel);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<PendingFile[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isStreaming = messages.some((m) => m.streaming);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || !connected) return;
    const attachments = files.length
      ? files.map((f) => ({ name: f.name, type: f.type, base64: f.base64 }))
      : undefined;
    sendMessage(text, undefined, attachments);
    setInput("");
    setFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-text-muted">
            <div className="text-center">
              <p className="text-4xl mb-3">&#128075;</p>
              <p className="text-lg font-medium">Chat with Clara</p>
              <p className="text-sm mt-1">Ask anything — memories, questions, or just chat.</p>
            </div>
          </div>
        )}
        <div className="py-4">
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border p-4">
        {!connected && (
          <p className="text-xs text-warning mb-2">Chat disconnected. Reconnecting...</p>
        )}
        <div className="flex items-end gap-2">
          <FileUpload
            files={files}
            onAdd={(newFiles) => setFiles((prev) => [...prev, ...newFiles])}
            onRemove={(i) => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
          />
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Clara..."
            rows={1}
            className="flex-1 resize-none bg-surface-overlay border border-border rounded-xl px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition"
          />
          {isStreaming ? (
            <button
              onClick={cancel}
              className="p-3 bg-danger/15 text-danger rounded-xl hover:bg-danger/25 transition"
              title="Stop generation"
            >
              <StopCircle size={20} />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim() || !connected}
              className="p-3 bg-accent hover:bg-accent-hover disabled:opacity-30 rounded-xl text-white transition"
              title="Send message"
            >
              <Send size={20} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
