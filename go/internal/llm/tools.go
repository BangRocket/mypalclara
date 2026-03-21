package llm

import (
	"encoding/json"
	"log"
)

// ToolCall represents a single tool call from an LLM response.
type ToolCall struct {
	ID           string         // unique identifier for the tool call
	Name         string         // name of the tool/function being called
	Arguments    map[string]any // parsed arguments
	RawArguments string         // original arguments string (for debugging)
}

// ToOpenAIFormat converts to OpenAI tool_call format.
func (tc ToolCall) ToOpenAIFormat() map[string]any {
	argsJSON, err := json.Marshal(tc.Arguments)
	if err != nil {
		argsJSON = []byte("{}")
	}
	return map[string]any{
		"id":   tc.ID,
		"type": "function",
		"function": map[string]any{
			"name":      tc.Name,
			"arguments": string(argsJSON),
		},
	}
}

// ToResultMessage creates a ToolResultMessage from this tool call's execution output.
func (tc ToolCall) ToResultMessage(output string) ToolResultMessage {
	return ToolResultMessage{ToolCallID: tc.ID, Content: output}
}

// ToolCallFromOpenAI parses a ToolCall from an OpenAI tool_call dict.
// Handles bad JSON gracefully by logging a warning and using an empty map.
func ToolCallFromOpenAI(d map[string]any) ToolCall {
	fn, _ := d["function"].(map[string]any)
	id, _ := d["id"].(string)
	name, _ := fn["name"].(string)
	argsRaw, _ := fn["arguments"].(string)

	var args map[string]any
	if argsRaw != "" {
		if err := json.Unmarshal([]byte(argsRaw), &args); err != nil {
			truncated := argsRaw
			if len(truncated) > 200 {
				truncated = truncated[:200]
			}
			log.Printf("WARNING: failed to parse tool call arguments for %s: %v. Raw arguments: %s", name, err, truncated)
			args = map[string]any{}
		}
	} else {
		args = map[string]any{}
	}

	return ToolCall{
		ID:           id,
		Name:         name,
		Arguments:    args,
		RawArguments: argsRaw,
	}
}

// ToolResponse is a unified response from an LLM with tool calling support.
type ToolResponse struct {
	Content    *string    // text content (may be nil if only tool calls)
	ToolCalls  []ToolCall // tool calls (empty if no tools called)
	StopReason string     // why the response ended (e.g., "end_turn", "tool_use")
	Raw        any        // original response object for debugging
}

// HasToolCalls reports whether the response contains tool calls.
func (r ToolResponse) HasToolCalls() bool {
	return len(r.ToolCalls) > 0
}

// ToAssistantMessage converts this response to an AssistantMessage.
func (r ToolResponse) ToAssistantMessage() AssistantMessage {
	tcs := make([]ToolCall, len(r.ToolCalls))
	copy(tcs, r.ToolCalls)
	return AssistantMessage{Content: r.Content, ToolCalls: tcs}
}

// ToolSchema describes a tool available for LLM use.
type ToolSchema struct {
	Name        string         // tool name
	Description string         // human-readable description
	Parameters  map[string]any // JSON Schema for the tool's parameters
}
