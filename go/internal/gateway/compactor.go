// Package gateway — compactor.go implements context window budget management
// via progressive summarization.
//
// Ported from mypalclara/core/context_compactor.py.
package gateway

import (
	"fmt"
	"strings"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

const (
	// DefaultBudgetRatio is the fraction of the context window budget used as
	// the compaction target.
	DefaultBudgetRatio = 0.6

	// compactThresholdRatio triggers compaction when tokens exceed
	// budget * budgetRatio * this value.
	compactThresholdRatio = 0.8

	// recentKeepRatio is the fraction of history messages to keep untouched
	// (the most recent ones).
	recentKeepRatio = 0.4

	// maxExcerptLen is the max characters extracted from each old message
	// for the summary.
	maxExcerptLen = 200
)

// Compactor manages context window budget via progressive summarization.
type Compactor struct {
	budgetRatio float64
}

// CompactionResult holds the output of a compaction attempt.
type CompactionResult struct {
	Messages     []llm.Message
	WasCompacted bool
	TokensSaved  int
}

// NewCompactor creates a Compactor with default settings.
func NewCompactor() *Compactor {
	return &Compactor{
		budgetRatio: DefaultBudgetRatio,
	}
}

// CompactIfNeeded checks if messages exceed the token budget and compacts if so.
//
// Logic:
//  1. Count tokens via llm.CountMessageTokens()
//  2. If under threshold (budget * budgetRatio * 0.8), return unchanged
//  3. Separate system messages from history
//  4. Keep last 40% of history untouched
//  5. For older messages: extract text excerpts
//  6. Create summary SystemMessage
//  7. Reassemble: system + summary + recent
func (c *Compactor) CompactIfNeeded(messages []llm.Message, budgetTokens int) CompactionResult {
	totalTokens := llm.CountMessageTokens(messages)
	threshold := int(float64(budgetTokens) * c.budgetRatio * compactThresholdRatio)

	if totalTokens <= threshold {
		return CompactionResult{
			Messages:     messages,
			WasCompacted: false,
			TokensSaved:  0,
		}
	}

	// Separate system messages (at the front) from the rest.
	var systemMsgs []llm.Message
	var history []llm.Message

	for i, msg := range messages {
		if msg.Role() == "system" && i < len(messages)-1 {
			// Only treat leading system messages as system; a system message
			// in the middle of conversation is part of history.
			if len(history) == 0 {
				systemMsgs = append(systemMsgs, msg)
				continue
			}
		}
		history = append(history, msg)
	}

	if len(history) <= 2 {
		// Not enough history to compact.
		return CompactionResult{
			Messages:     messages,
			WasCompacted: false,
			TokensSaved:  0,
		}
	}

	// Split history into old (to summarize) and recent (to keep).
	keepCount := int(float64(len(history)) * recentKeepRatio)
	if keepCount < 1 {
		keepCount = 1
	}
	splitIdx := len(history) - keepCount
	if splitIdx < 1 {
		splitIdx = 1
	}

	oldMsgs := history[:splitIdx]
	recentMsgs := history[splitIdx:]

	// Build summary from old messages.
	var excerpts []string
	for _, msg := range oldMsgs {
		text := messageText(msg)
		if text == "" {
			continue
		}
		if len(text) > maxExcerptLen {
			text = text[:maxExcerptLen]
		}
		role := msg.Role()
		excerpts = append(excerpts, fmt.Sprintf("[%s]: %s", role, text))
	}

	summaryText := fmt.Sprintf(
		"[Summary of earlier conversation (%d messages compressed)]\n%s",
		len(oldMsgs),
		strings.Join(excerpts, "\n"),
	)
	summaryMsg := llm.SystemMessage{Content: summaryText}

	// Reassemble.
	result := make([]llm.Message, 0, len(systemMsgs)+1+len(recentMsgs))
	result = append(result, systemMsgs...)
	result = append(result, summaryMsg)
	result = append(result, recentMsgs...)

	newTokens := llm.CountMessageTokens(result)
	saved := totalTokens - newTokens
	if saved < 0 {
		saved = 0
	}

	return CompactionResult{
		Messages:     result,
		WasCompacted: true,
		TokensSaved:  saved,
	}
}

// messageText extracts text content from a message for summarization.
func messageText(msg llm.Message) string {
	switch m := msg.(type) {
	case llm.SystemMessage:
		return m.Content
	case llm.UserMessage:
		return m.Content
	case llm.AssistantMessage:
		if m.Content != nil {
			return *m.Content
		}
		return ""
	case llm.ToolResultMessage:
		return m.Content
	default:
		return ""
	}
}
