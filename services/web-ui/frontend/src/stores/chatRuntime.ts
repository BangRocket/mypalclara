/**
 * Convert our StreamMessage + ToolEvent[] into assistant-ui's ThreadMessageLike.
 *
 * This is the critical bridge between our WebSocket protocol and assistant-ui's
 * internal message format.
 */

import type { MessageStatus } from "@assistant-ui/react";
import type { StreamMessage, ToolEvent } from "./chatStore";

function toolEventToContentPart(tool: ToolEvent, index: number) {
  return {
    type: "tool-call" as const,
    toolCallId: `${tool.tool_name}-${tool.step ?? index}`,
    toolName: tool.tool_name,
    argsText: tool.description ?? undefined,
    result: tool.output_preview ?? undefined,
    isError: tool.success === undefined ? undefined : !tool.success,
  };
}

export function convertMessage(msg: StreamMessage, _idx: number) {
  if (msg.role === "user") {
    return {
      role: "user" as const,
      id: msg.id,
      content: [{ type: "text" as const, text: msg.content }],
    };
  }

  // Build content parts: tool calls + text
  const content: unknown[] = [];

  for (let i = 0; i < msg.tools.length; i++) {
    content.push(toolEventToContentPart(msg.tools[i], i));
  }

  if (msg.content) {
    content.push({ type: "text" as const, text: msg.content });
  }

  const status: MessageStatus = msg.streaming
    ? { type: "running" }
    : { type: "complete", reason: "stop" };

  return {
    role: "assistant" as const,
    id: msg.id,
    content,
    status,
  };
}
