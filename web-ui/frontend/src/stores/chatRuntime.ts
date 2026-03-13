/**
 * Convert our ChatMessage + ToolEvent[] into assistant-ui's ThreadMessageLike.
 *
 * This is the critical bridge between our WebSocket protocol and assistant-ui's
 * internal message format.
 */

import type { MessageStatus } from "@assistant-ui/react";
import type { ChatMessage, ToolEvent } from "./chatStore";

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

export function convertMessage(msg: ChatMessage, _idx: number) {
  if (msg.role === "user") {
    const result: Record<string, unknown> = {
      role: "user" as const,
      id: msg.id,
      content: [{ type: "text" as const, text: msg.content }],
    };

    // Include attachments if present so they render in message history
    if (msg.attachments && msg.attachments.length > 0) {
      result.attachments = msg.attachments;
    }

    return result;
  }

  // Build content parts: tool calls + text
  const content: unknown[] = [];
  const tools = msg.toolEvents ?? [];

  for (let i = 0; i < tools.length; i++) {
    content.push(toolEventToContentPart(tools[i], i));
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
