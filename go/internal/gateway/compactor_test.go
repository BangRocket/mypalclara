package gateway

import (
	"strings"
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

func TestCompactNotNeeded(t *testing.T) {
	c := NewCompactor()

	msgs := []llm.Message{
		llm.SystemMessage{Content: "You are Clara."},
		llm.UserMessage{Content: "Hello!"},
		llm.AssistantMessage{Content: strPtr("Hi there!")},
	}

	// Use a huge budget so compaction is not needed.
	result := c.CompactIfNeeded(msgs, 100_000)

	if result.WasCompacted {
		t.Error("expected no compaction for short conversation")
	}
	if len(result.Messages) != len(msgs) {
		t.Errorf("expected %d messages unchanged, got %d", len(msgs), len(result.Messages))
	}
	if result.TokensSaved != 0 {
		t.Errorf("expected 0 tokens saved, got %d", result.TokensSaved)
	}
}

func TestCompactTruncatesOld(t *testing.T) {
	c := NewCompactor()

	// Build a conversation with many messages so it exceeds a tight budget.
	msgs := []llm.Message{
		llm.SystemMessage{Content: "You are Clara, a helpful assistant."},
	}

	// Add 50 user/assistant exchanges with substantial content.
	for i := 0; i < 50; i++ {
		msgs = append(msgs,
			llm.UserMessage{Content: strings.Repeat("This is a fairly long user message to inflate token count. ", 10)},
			llm.AssistantMessage{Content: strPtr(strings.Repeat("This is a fairly long assistant response to inflate token count. ", 10))},
		)
	}

	// Count actual tokens.
	totalTokens := llm.CountMessageTokens(msgs)

	// Set budget so that 60% of it (the threshold) is less than total tokens.
	// budgetRatio=0.6, threshold = budget * 0.6 * 0.8
	// We want: totalTokens > budget * 0.48
	// So budget = totalTokens / 0.48 * 0.9 (ensure it triggers)
	budget := int(float64(totalTokens) / 0.48 * 0.9)

	result := c.CompactIfNeeded(msgs, budget)

	if !result.WasCompacted {
		t.Error("expected compaction for long conversation")
	}
	if result.TokensSaved <= 0 {
		t.Error("expected positive tokens saved")
	}

	// Result should have fewer messages than original.
	if len(result.Messages) >= len(msgs) {
		t.Errorf("expected fewer messages after compaction, got %d (was %d)", len(result.Messages), len(msgs))
	}

	// First message should still be a system message.
	if result.Messages[0].Role() != "system" {
		t.Errorf("expected first message to be system, got %s", result.Messages[0].Role())
	}

	// Should contain a summary system message.
	foundSummary := false
	for _, msg := range result.Messages {
		if sys, ok := msg.(llm.SystemMessage); ok {
			if strings.Contains(sys.Content, "Summary of earlier conversation") {
				foundSummary = true
				break
			}
		}
	}
	if !foundSummary {
		t.Error("expected a summary system message in compacted output")
	}
}

// strPtr is defined in orchestrator_test.go
