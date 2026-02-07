import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";
import type { StreamMessage } from "@/stores/chatStore";
import { ToolCallDisplay } from "./ToolCallDisplay";

interface MessageBubbleProps {
  message: StreamMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 px-4 py-3", isUser ? "justify-end" : "")}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent shrink-0">
          C
        </div>
      )}

      <div
        className={cn(
          "max-w-[75%] rounded-xl px-4 py-3",
          isUser
            ? "bg-accent/15 text-text-primary"
            : "bg-surface-raised border border-border text-text-primary",
        )}
      >
        {/* Tool calls */}
        {message.tools.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.tools.map((t, i) => (
              <ToolCallDisplay key={i} tool={t} />
            ))}
          </div>
        )}

        {/* Content */}
        {message.content && (
          <div className="prose prose-invert prose-sm max-w-none [&_p]:my-1">
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const code = String(children).replace(/\n$/, "");
                  if (match) {
                    return (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ margin: 0, borderRadius: "8px", fontSize: "13px" }}
                      >
                        {code}
                      </SyntaxHighlighter>
                    );
                  }
                  return (
                    <code className="bg-surface-overlay px-1.5 py-0.5 rounded text-accent text-xs font-mono" {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </Markdown>
          </div>
        )}

        {/* Streaming indicator */}
        {message.streaming && !message.content && (
          <span className="inline-flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse [animation-delay:300ms]" />
          </span>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-surface-overlay flex items-center justify-center text-xs font-bold text-text-secondary shrink-0">
          U
        </div>
      )}
    </div>
  );
}
