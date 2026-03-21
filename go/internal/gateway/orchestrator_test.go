package gateway

import (
	"context"
	"strings"
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// --- mock provider ---

type mockProvider struct {
	// responses is a queue of ToolResponses returned by CompleteWithTools.
	responses []*llm.ToolResponse
	callIdx   int

	// completeResult is returned by Complete (synthesis call).
	completeResult string
	completeErr    error

	// Track calls for assertions.
	completeWithToolsCalls int
	completeCalls          int
}

func (m *mockProvider) Name() string { return "mock" }

func (m *mockProvider) Complete(_ context.Context, _ []llm.Message, _ *llm.LLMConfig) (string, error) {
	m.completeCalls++
	return m.completeResult, m.completeErr
}

func (m *mockProvider) CompleteWithTools(_ context.Context, _ []llm.Message, _ []llm.ToolSchema, _ *llm.LLMConfig) (*llm.ToolResponse, error) {
	m.completeWithToolsCalls++
	if m.callIdx >= len(m.responses) {
		// Fallback: return empty content, no tools.
		empty := ""
		return &llm.ToolResponse{Content: &empty}, nil
	}
	resp := m.responses[m.callIdx]
	m.callIdx++
	return resp, nil
}

// --- mock tool executor ---

type mockToolExecutor struct {
	results map[string]string
	errors  map[string]error
	calls   []string
}

func (m *mockToolExecutor) Execute(_ context.Context, toolName string, _ map[string]any, _ string) (string, error) {
	m.calls = append(m.calls, toolName)
	if e, ok := m.errors[toolName]; ok {
		return "", e
	}
	if r, ok := m.results[toolName]; ok {
		return r, nil
	}
	return "ok", nil
}

// --- helpers ---

func collectEvents(events *[]Event) func(Event) {
	return func(e Event) {
		*events = append(*events, e)
	}
}

func strPtr(s string) *string { return &s }

// --- tests ---

func TestGenerateWithToolsNoTools(t *testing.T) {
	provider := &mockProvider{
		responses: []*llm.ToolResponse{
			{Content: strPtr("Hello, world!")},
		},
	}
	executor := &mockToolExecutor{results: map[string]string{}}

	orch := NewOrchestrator(provider, executor)
	var events []Event
	result, err := orch.GenerateWithTools(
		context.Background(),
		[]llm.Message{llm.UserMessage{Content: "Hi"}},
		nil, "user1", "",
		collectEvents(&events),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Hello, world!" {
		t.Fatalf("expected 'Hello, world!', got %q", result)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	if events[0].Type != "complete" {
		t.Fatalf("expected 'complete' event, got %q", events[0].Type)
	}
	if events[0].ToolCount != 0 {
		t.Fatalf("expected ToolCount 0, got %d", events[0].ToolCount)
	}
	if provider.completeCalls != 0 {
		t.Fatalf("synthesis call should not have been made, but Complete was called %d times", provider.completeCalls)
	}
}

func TestGenerateWithToolsOneRound(t *testing.T) {
	// First call: LLM requests a tool call.
	// Second call: LLM returns final text.
	provider := &mockProvider{
		responses: []*llm.ToolResponse{
			{
				Content: nil,
				ToolCalls: []llm.ToolCall{
					{ID: "tc1", Name: "search", Arguments: map[string]any{"query": "go"}},
				},
			},
			{Content: strPtr("Found results for Go.")},
		},
	}
	executor := &mockToolExecutor{
		results: map[string]string{"search": "Go is a programming language."},
	}

	orch := NewOrchestrator(provider, executor)
	var events []Event
	result, err := orch.GenerateWithTools(
		context.Background(),
		[]llm.Message{llm.UserMessage{Content: "Search for Go"}},
		nil, "user1", "",
		collectEvents(&events),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Found results for Go." {
		t.Fatalf("unexpected result: %q", result)
	}

	// Expect: tool_start, tool_result, complete
	if len(events) != 3 {
		t.Fatalf("expected 3 events, got %d: %+v", len(events), events)
	}
	if events[0].Type != "tool_start" || events[0].ToolName != "search" || events[0].Step != 1 {
		t.Fatalf("bad tool_start event: %+v", events[0])
	}
	if events[1].Type != "tool_result" || events[1].ToolName != "search" || !events[1].Success {
		t.Fatalf("bad tool_result event: %+v", events[1])
	}
	if events[2].Type != "complete" || events[2].ToolCount != 1 {
		t.Fatalf("bad complete event: %+v", events[2])
	}

	// Tool executor should have been called once.
	if len(executor.calls) != 1 || executor.calls[0] != "search" {
		t.Fatalf("expected one 'search' call, got %v", executor.calls)
	}
}

func TestGenerateWithToolsSynthesisCall(t *testing.T) {
	// First call: tool call returned.
	// Second call: empty content after tools ran => triggers synthesis.
	provider := &mockProvider{
		responses: []*llm.ToolResponse{
			{
				Content: nil,
				ToolCalls: []llm.ToolCall{
					{ID: "tc1", Name: "read_file", Arguments: map[string]any{"path": "/tmp/x"}},
				},
			},
			{Content: strPtr("")}, // empty content after tools
		},
		completeResult: "Here is a summary of the file.",
	}
	executor := &mockToolExecutor{
		results: map[string]string{"read_file": "file contents here"},
	}

	orch := NewOrchestrator(provider, executor)
	var events []Event
	result, err := orch.GenerateWithTools(
		context.Background(),
		[]llm.Message{llm.UserMessage{Content: "Read the file"}},
		nil, "user1", "",
		collectEvents(&events),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Here is a summary of the file." {
		t.Fatalf("expected synthesis result, got %q", result)
	}
	if provider.completeCalls != 1 {
		t.Fatalf("expected 1 synthesis call, got %d", provider.completeCalls)
	}
}

func TestGenerateWithToolsNoReply(t *testing.T) {
	provider := &mockProvider{
		responses: []*llm.ToolResponse{
			{Content: strPtr("  NO_REPLY  ")},
		},
	}
	executor := &mockToolExecutor{results: map[string]string{}}

	orch := NewOrchestrator(provider, executor)
	var events []Event
	result, err := orch.GenerateWithTools(
		context.Background(),
		[]llm.Message{llm.UserMessage{Content: "Hi"}},
		nil, "user1", "",
		collectEvents(&events),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "" {
		t.Fatalf("expected empty string for NO_REPLY, got %q", result)
	}
}

func TestIsNoReply(t *testing.T) {
	tests := []struct {
		input string
		want  bool
	}{
		{"NO_REPLY", true},
		{"  NO_REPLY  ", true},
		{"\tNO_REPLY\n", true},
		{"no_reply", false},    // case sensitive
		{"NO_REPLY!", false},   // extra char
		{"NO REPLY", false},    // space, not underscore
		{"Hello", false},       // normal text
		{"", false},            // empty
		{"NO_REPLY\nHi", false}, // extra content
	}

	for _, tt := range tests {
		got := IsNoReply(tt.input)
		if got != tt.want {
			t.Errorf("IsNoReply(%q) = %v, want %v", tt.input, got, tt.want)
		}
	}
}

func TestWrapUntrusted(t *testing.T) {
	result := WrapUntrusted("hello <script>alert(1)</script>", "tool_search")

	// Must contain the security notice.
	if !strings.Contains(result, "[NOTICE:") {
		t.Fatal("missing security notice")
	}

	// Must escape angle brackets.
	if strings.Contains(result, "<script>") {
		t.Fatal("angle brackets not escaped")
	}
	if !strings.Contains(result, "&lt;script>") {
		t.Fatal("expected escaped angle bracket")
	}

	// Must be wrapped in untrusted tags.
	if !strings.HasPrefix(result, "<untrusted_tool_search>") {
		t.Fatalf("missing opening tag, got: %s", result[:50])
	}
	if !strings.HasSuffix(result, "</untrusted_tool_search>") {
		t.Fatalf("missing closing tag")
	}
}

func TestWrapUntrustedPreservesContent(t *testing.T) {
	result := WrapUntrusted("normal text without brackets", "tool_read")
	if !strings.Contains(result, "normal text without brackets") {
		t.Fatal("content not preserved")
	}
}

func TestGenerateWithToolsTruncation(t *testing.T) {
	// Tool returns content longer than MaxToolResultChars.
	longOutput := strings.Repeat("x", MaxToolResultChars+100)

	provider := &mockProvider{
		responses: []*llm.ToolResponse{
			{
				Content: nil,
				ToolCalls: []llm.ToolCall{
					{ID: "tc1", Name: "big_tool", Arguments: map[string]any{}},
				},
			},
			{Content: strPtr("Done.")},
		},
	}
	executor := &mockToolExecutor{
		results: map[string]string{"big_tool": longOutput},
	}

	orch := NewOrchestrator(provider, executor)
	var events []Event
	result, err := orch.GenerateWithTools(
		context.Background(),
		[]llm.Message{llm.UserMessage{Content: "Go"}},
		nil, "user1", "",
		collectEvents(&events),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Done." {
		t.Fatalf("unexpected result: %q", result)
	}

	// The tool_result preview should exist and the truncation marker should be in the wrapped output.
	if len(events) < 2 {
		t.Fatalf("expected at least 2 events, got %d", len(events))
	}
}
