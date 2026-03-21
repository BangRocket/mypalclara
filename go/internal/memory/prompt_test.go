package memory

import (
	"testing"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

func TestBuildPromptBasic(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		UserMessage: "Hello Clara!",
	})

	// Should have at least system + user message.
	if len(msgs) < 2 {
		t.Fatalf("expected at least 2 messages, got %d", len(msgs))
	}

	// First message must be system (persona).
	if msgs[0].Role() != "system" {
		t.Errorf("first message role = %q, want %q", msgs[0].Role(), "system")
	}

	// Last message must be the user message.
	last := msgs[len(msgs)-1]
	if last.Role() != "user" {
		t.Errorf("last message role = %q, want %q", last.Role(), "user")
	}
	um, ok := last.(llm.UserMessage)
	if !ok {
		t.Fatalf("last message is %T, want llm.UserMessage", last)
	}
	if um.Content != "Hello Clara!" {
		t.Errorf("last message content = %q, want %q", um.Content, "Hello Clara!")
	}

	// Persona should contain Clara's name.
	sys, ok := msgs[0].(llm.SystemMessage)
	if !ok {
		t.Fatalf("first message is %T, want llm.SystemMessage", msgs[0])
	}
	if !contains(sys.Content, "Clara") {
		t.Error("persona does not contain 'Clara'")
	}
}

func TestBuildPromptWithMemories(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		UserMemories:    []string{"Likes Go programming", "Has a cat named Whiskers"},
		ProjectMemories: []string{"Working on MyPalClara Go port"},
		UserMessage:     "What should I work on?",
	})

	// Should have system (persona) + system (context) + user message = 3 minimum.
	if len(msgs) < 3 {
		t.Fatalf("expected at least 3 messages, got %d", len(msgs))
	}

	// Second message should be the context system message.
	ctx, ok := msgs[1].(llm.SystemMessage)
	if !ok {
		t.Fatalf("second message is %T, want llm.SystemMessage", msgs[1])
	}

	// Should contain user memories section.
	if !contains(ctx.Content, "What I Remember About You") {
		t.Error("context missing 'What I Remember About You' section")
	}
	if !contains(ctx.Content, "Likes Go programming") {
		t.Error("context missing user memory content")
	}
	if !contains(ctx.Content, "Has a cat named Whiskers") {
		t.Error("context missing second user memory")
	}

	// Should contain project memories section.
	if !contains(ctx.Content, "Project Context") {
		t.Error("context missing 'Project Context' section")
	}
	if !contains(ctx.Content, "Working on MyPalClara Go port") {
		t.Error("context missing project memory content")
	}
}

func TestBuildPromptWithHistory(t *testing.T) {
	pb := NewPromptBuilder("clara")

	now := time.Now().UTC()

	msgs := pb.BuildPrompt(PromptOptions{
		RecentMessages: []SessionMessage{
			{Role: "user", Content: "Hi there", CreatedAt: now.Add(-2 * time.Minute)},
			{Role: "assistant", Content: "Hello! How can I help?", CreatedAt: now.Add(-1 * time.Minute)},
		},
		UserMessage: "Tell me a joke",
	})

	// System + history(user) + history(assistant) + current user = 4.
	if len(msgs) < 4 {
		t.Fatalf("expected at least 4 messages, got %d", len(msgs))
	}

	// Check history messages are in correct order and roles.
	// After the system message(s), we should have: user, assistant, user.
	var historyRoles []string
	for _, m := range msgs[1:] { // skip persona system msg
		if m.Role() == "system" {
			continue // skip context system msg if present
		}
		historyRoles = append(historyRoles, m.Role())
	}

	expected := []string{"user", "assistant", "user"}
	if len(historyRoles) != len(expected) {
		t.Fatalf("history roles = %v, want %v", historyRoles, expected)
	}
	for i, role := range historyRoles {
		if role != expected[i] {
			t.Errorf("history role[%d] = %q, want %q", i, role, expected[i])
		}
	}

	// The history user message should have a timestamp prefix.
	histUser := msgs[1]
	if histUser.Role() == "system" {
		// Context system message present, history starts at index 2.
		histUser = msgs[2]
	}
	um, ok := histUser.(llm.UserMessage)
	if !ok {
		t.Fatalf("history user message is %T, want llm.UserMessage", histUser)
	}
	if !contains(um.Content, "Hi there") {
		t.Errorf("history user content = %q, should contain 'Hi there'", um.Content)
	}

	// Last message should be the current user message.
	last := msgs[len(msgs)-1].(llm.UserMessage)
	if last.Content != "Tell me a joke" {
		t.Errorf("last message content = %q, want %q", last.Content, "Tell me a joke")
	}
}

func TestBuildPromptMessageOrder(t *testing.T) {
	pb := NewPromptBuilder("clara")

	now := time.Now().UTC()

	msgs := pb.BuildPrompt(PromptOptions{
		UserMemories:   []string{"Prefers dark mode"},
		SessionSummary: "We discussed Go testing patterns",
		RecentMessages: []SessionMessage{
			{Role: "user", Content: "prev question", CreatedAt: now.Add(-1 * time.Minute)},
			{Role: "assistant", Content: "prev answer", CreatedAt: now},
		},
		UserMessage: "new question",
		ModelName:   "claude-sonnet-4-5",
	})

	// Expected order:
	// [0] system (persona)
	// [1] system (context: memories + summary)
	// [2] user (history)
	// [3] assistant (history)
	// [4] user (current)

	if len(msgs) != 5 {
		t.Fatalf("expected 5 messages, got %d", len(msgs))
	}

	// First must be system.
	if msgs[0].Role() != "system" {
		t.Errorf("msgs[0].Role() = %q, want %q", msgs[0].Role(), "system")
	}

	// Second must be system (context).
	if msgs[1].Role() != "system" {
		t.Errorf("msgs[1].Role() = %q, want %q", msgs[1].Role(), "system")
	}

	// Context should contain both memories and summary.
	ctx := msgs[1].(llm.SystemMessage)
	if !contains(ctx.Content, "Prefers dark mode") {
		t.Error("context missing user memory")
	}
	if !contains(ctx.Content, "Previous Conversation Summary") {
		t.Error("context missing session summary header")
	}
	if !contains(ctx.Content, "We discussed Go testing patterns") {
		t.Error("context missing session summary content")
	}

	// History messages.
	if msgs[2].Role() != "user" {
		t.Errorf("msgs[2].Role() = %q, want %q", msgs[2].Role(), "user")
	}
	if msgs[3].Role() != "assistant" {
		t.Errorf("msgs[3].Role() = %q, want %q", msgs[3].Role(), "assistant")
	}

	// Last must be user (current message).
	if msgs[4].Role() != "user" {
		t.Errorf("msgs[4].Role() = %q, want %q", msgs[4].Role(), "user")
	}
	um := msgs[4].(llm.UserMessage)
	if um.Content != "new question" {
		t.Errorf("last message content = %q, want %q", um.Content, "new question")
	}
}

func TestBuildPromptWithGraphRelations(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		GraphRelations: []GraphRelation{
			{Source: "Josh", Relationship: "works_at", Destination: "Anthropic"},
			{Source: "Josh", Relationship: "owns", Destination: "Whiskers"},
		},
		UserMessage: "Tell me about Josh",
	})

	// Find context message.
	var ctx llm.SystemMessage
	found := false
	for _, m := range msgs {
		if sm, ok := m.(llm.SystemMessage); ok && contains(sm.Content, "Relationship Context") {
			ctx = sm
			found = true
			break
		}
	}
	if !found {
		t.Fatal("no system message with 'Relationship Context'")
	}

	if !contains(ctx.Content, "Josh") {
		t.Error("graph context missing 'Josh'")
	}
	if !contains(ctx.Content, "works at") {
		t.Error("graph context missing 'works at' (snake_case should be converted)")
	}
	if !contains(ctx.Content, "Anthropic") {
		t.Error("graph context missing 'Anthropic'")
	}
}

func TestBuildPromptWithSessionSummary(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		SessionSummary: "User asked about Go concurrency patterns and goroutine lifecycle.",
		UserMessage:    "Continue from where we left off",
	})

	// Find context message with summary.
	var ctx llm.SystemMessage
	found := false
	for _, m := range msgs {
		if sm, ok := m.(llm.SystemMessage); ok && contains(sm.Content, "Previous Conversation Summary") {
			ctx = sm
			found = true
			break
		}
	}
	if !found {
		t.Fatal("no system message with 'Previous Conversation Summary'")
	}

	if !contains(ctx.Content, "Go concurrency patterns") {
		t.Error("summary missing expected content")
	}
}

func TestBuildPromptPersonaContainsDateTime(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		UserMessage: "What time is it?",
	})

	persona := msgs[0].(llm.SystemMessage)
	if !contains(persona.Content, "Current Date & Time") {
		t.Error("persona missing 'Current Date & Time' section")
	}
	if !contains(persona.Content, "UTC") {
		t.Error("persona missing UTC timestamp")
	}
}

func TestBuildPromptNoContextWhenEmpty(t *testing.T) {
	pb := NewPromptBuilder("clara")

	msgs := pb.BuildPrompt(PromptOptions{
		UserMessage: "Just say hello",
	})

	// With no memories, summary, or history, should have exactly 2 messages:
	// system (persona) + user.
	if len(msgs) != 2 {
		t.Errorf("expected 2 messages (no context), got %d", len(msgs))
	}
}

func TestFormatGraphRelationsDedup(t *testing.T) {
	relations := []GraphRelation{
		{Source: "Josh", Relationship: "owns", Destination: "Whiskers"},
		{Source: "josh", Relationship: "owns", Destination: "whiskers"}, // duplicate (case-insensitive)
	}

	result := formatGraphRelations(relations)
	count := len(splitNonEmpty(result, "\n"))
	if count != 1 {
		t.Errorf("expected 1 deduplicated relation, got %d", count)
	}
}

func TestFormatGraphRelationsSkipsIncomplete(t *testing.T) {
	relations := []GraphRelation{
		{Source: "Josh", Relationship: "", Destination: "Whiskers"},  // missing relationship
		{Source: "", Relationship: "owns", Destination: "Whiskers"},  // missing source
		{Source: "Josh", Relationship: "owns", Destination: ""},      // missing destination
		{Source: "Josh", Relationship: "owns", Destination: "Cat"},   // valid
	}

	result := formatGraphRelations(relations)
	count := len(splitNonEmpty(result, "\n"))
	if count != 1 {
		t.Errorf("expected 1 valid relation, got %d", count)
	}
}

// contains checks if s contains substr (case-sensitive).
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 ||
		(len(s) > 0 && len(substr) > 0 && findSubstring(s, substr)))
}

func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// splitNonEmpty splits s by sep and returns only non-empty parts.
func splitNonEmpty(s, sep string) []string {
	parts := splitString(s, sep)
	var result []string
	for _, p := range parts {
		if trimSpace(p) != "" {
			result = append(result, p)
		}
	}
	return result
}

func splitString(s, sep string) []string {
	if s == "" {
		return nil
	}
	var parts []string
	for {
		i := indexString(s, sep)
		if i < 0 {
			parts = append(parts, s)
			break
		}
		parts = append(parts, s[:i])
		s = s[i+len(sep):]
	}
	return parts
}

func indexString(s, sub string) int {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func trimSpace(s string) string {
	start := 0
	for start < len(s) && (s[start] == ' ' || s[start] == '\t' || s[start] == '\n' || s[start] == '\r') {
		start++
	}
	end := len(s)
	for end > start && (s[end-1] == ' ' || s[end-1] == '\t' || s[end-1] == '\n' || s[end-1] == '\r') {
		end--
	}
	return s[start:end]
}
