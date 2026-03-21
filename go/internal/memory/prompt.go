package memory

import (
	"fmt"
	"strings"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// PromptBuilder constructs LLM prompts with Clara's persona and context.
type PromptBuilder struct {
	botName   string
	maxTokens int
}

// NewPromptBuilder creates a PromptBuilder for the given bot name.
func NewPromptBuilder(botName string) *PromptBuilder {
	return &PromptBuilder{
		botName:   botName,
		maxTokens: 0, // 0 means use model default
	}
}

// PromptOptions holds all context for building a prompt.
type PromptOptions struct {
	UserMemories     []string
	ProjectMemories  []string
	SessionSummary   string
	RecentMessages   []SessionMessage
	UserMessage      string
	GraphRelations   []GraphRelation
	EmotionalContext []map[string]any
	RecurringTopics  []map[string]any
	ChannelContext   []SessionMessage
	PrivacyScope     string // "full" or "public_only"
	UserID           string
	ModelName        string
}

// BuildPrompt creates the full message list for the LLM.
//
// Returns: [SystemMessage(persona), SystemMessage(context), ...history..., UserMessage(current)]
//
// Section ordering matches the Python prompt_builder.py:
//
//	persona → user memories → project memories → graph relations →
//	emotional context → recurring topics → session summary →
//	channel context → history → current message
func (b *PromptBuilder) BuildPrompt(opts PromptOptions) []llm.Message {
	// 1. Build persona system message with date/time and user context.
	persona := b.buildPersona(opts)

	// 2. Build context sections.
	contextParts := b.buildContextSections(opts)

	// 3. Assemble messages.
	messages := []llm.Message{
		llm.SystemMessage{Content: persona},
	}

	if len(contextParts) > 0 {
		messages = append(messages, llm.SystemMessage{Content: strings.Join(contextParts, "\n\n")})
	}

	// 4. Add recent conversation history as alternating user/assistant messages.
	for _, msg := range opts.RecentMessages {
		switch msg.Role {
		case "user":
			ts := formatMessageTimestamp(msg.CreatedAt)
			content := msg.Content
			if ts != "" {
				content = fmt.Sprintf("[%s] %s", ts, content)
			}
			messages = append(messages, llm.UserMessage{Content: content})
		case "assistant":
			messages = append(messages, llm.AssistantMessage{Content: strPtr(msg.Content)})
		}
	}

	// 5. Add current user message.
	messages = append(messages, llm.UserMessage{Content: opts.UserMessage})

	// 6. Trim to token budget (80% of context window).
	messages = b.trimToBudget(messages, opts.ModelName)

	return messages
}

// buildPersona constructs the persona system message text.
func (b *PromptBuilder) buildPersona(opts PromptOptions) string {
	parts := []string{ClaraPersona}

	// Current date/time.
	now := time.Now().UTC().Format("2006-01-02 15:04:05 UTC")
	parts = append(parts, fmt.Sprintf("## Current Date & Time\nCurrent: %s", now))

	// User context.
	if opts.UserID != "" {
		parts = append(parts, fmt.Sprintf("## User Context\nUser ID: %s", opts.UserID))
	}

	return strings.Join(parts, "\n\n")
}

// buildContextSections assembles the context sections in order.
func (b *PromptBuilder) buildContextSections(opts PromptOptions) []string {
	var parts []string

	// User memories.
	if len(opts.UserMemories) > 0 {
		lines := make([]string, len(opts.UserMemories))
		for i, m := range opts.UserMemories {
			lines[i] = "- " + m
		}
		parts = append(parts, "## What I Remember About You\n"+strings.Join(lines, "\n"))
	}

	// Project memories.
	if len(opts.ProjectMemories) > 0 {
		lines := make([]string, len(opts.ProjectMemories))
		for i, m := range opts.ProjectMemories {
			lines[i] = "- " + m
		}
		parts = append(parts, "## Project Context\n"+strings.Join(lines, "\n"))
	}

	// Graph relations.
	if len(opts.GraphRelations) > 0 {
		block := formatGraphRelations(opts.GraphRelations)
		if block != "" {
			parts = append(parts, "## Relationship Context\n"+block)
		}
	}

	// Emotional context.
	if len(opts.EmotionalContext) > 0 {
		block := formatEmotionalContext(opts.EmotionalContext)
		if block != "" {
			parts = append(parts, "## Recent Emotional Context\n"+block)
		}
	}

	// Recurring topics.
	if len(opts.RecurringTopics) > 0 {
		block := formatRecurringTopics(opts.RecurringTopics)
		if block != "" {
			parts = append(parts, "## Recurring Topics\n"+block)
		}
	}

	// Session summary (previous conversation).
	if opts.SessionSummary != "" {
		parts = append(parts, "## Previous Conversation Summary\n"+opts.SessionSummary)
	}

	// Channel context.
	if len(opts.ChannelContext) > 0 {
		block := formatChannelContext(opts.ChannelContext)
		if block != "" {
			parts = append(parts, block)
		}
	}

	return parts
}

// trimToBudget trims messages to fit within 80% of the model's context window.
// Removes oldest history messages first, never removes system messages or the
// final user message.
func (b *PromptBuilder) trimToBudget(messages []llm.Message, modelName string) []llm.Message {
	if modelName == "" {
		modelName = "claude"
	}

	maxTokens := b.maxTokens
	if maxTokens == 0 {
		maxTokens = int(float64(llm.GetContextWindow(modelName)) * 0.8)
	}

	total := llm.CountMessageTokens(messages)
	if total <= maxTokens {
		return messages
	}

	// Find the first non-system message (start of history).
	firstHistory := 0
	for i, m := range messages {
		if _, ok := m.(llm.SystemMessage); !ok {
			firstHistory = i
			break
		}
	}

	// Remove oldest history messages, keeping at least the final user message.
	for firstHistory < len(messages)-1 && llm.CountMessageTokens(messages) > maxTokens {
		messages = append(messages[:firstHistory], messages[firstHistory+1:]...)
	}

	return messages
}

// formatGraphRelations formats graph relations for the prompt.
func formatGraphRelations(relations []GraphRelation) string {
	if len(relations) == 0 {
		return ""
	}

	seen := make(map[string]bool)
	var lines []string

	for _, rel := range relations {
		if rel.Source == "" || rel.Relationship == "" || rel.Destination == "" {
			continue
		}

		readableRel := strings.ToLower(strings.ReplaceAll(rel.Relationship, "_", " "))
		key := strings.ToLower(rel.Source) + "|" + readableRel + "|" + strings.ToLower(rel.Destination)
		if seen[key] {
			continue
		}
		seen[key] = true

		lines = append(lines, fmt.Sprintf("- %s → %s → %s", rel.Source, readableRel, rel.Destination))
	}

	return strings.Join(lines, "\n")
}

// formatEmotionalContext formats emotional context entries for the prompt.
func formatEmotionalContext(contexts []map[string]any) string {
	var lines []string
	for _, ctx := range contexts {
		memory, _ := ctx["memory"].(string)
		if memory == "" {
			continue
		}

		arc, _ := ctx["arc"].(string)
		if arc == "" {
			arc = "stable"
		}
		energy, _ := ctx["energy"].(string)
		if energy == "" {
			energy = "neutral"
		}

		// Skip stable/neutral — not worth mentioning.
		if arc == "stable" && (energy == "neutral" || energy == "casual") {
			continue
		}

		channelName, _ := ctx["channel_name"].(string)
		isDM, _ := ctx["is_dm"].(bool)

		var channelHint string
		if isDM {
			channelHint = "DM"
		} else if channelName != "" {
			if !strings.HasPrefix(channelName, "#") {
				channelHint = "#" + channelName
			} else {
				channelHint = channelName
			}
		} else {
			channelHint = "unknown"
		}

		lines = append(lines, fmt.Sprintf("- [%s] %s", channelHint, memory))
	}

	return strings.Join(lines, "\n")
}

// formatRecurringTopics formats recurring topic patterns for the prompt.
func formatRecurringTopics(topics []map[string]any) string {
	var lines []string

	limit := 3
	if len(topics) < limit {
		limit = len(topics)
	}

	for _, topic := range topics[:limit] {
		topicName, _ := topic["topic"].(string)
		if topicName == "" {
			continue
		}

		mentionCount := 0
		if mc, ok := topic["mention_count"].(int); ok {
			mentionCount = mc
		}
		if mentionCount < 2 {
			continue
		}

		patternNote, _ := topic["pattern_note"].(string)
		if patternNote != "" {
			lines = append(lines, fmt.Sprintf("- %s: %s", topicName, patternNote))
		} else {
			lines = append(lines, fmt.Sprintf("- %s: mentioned %d times", topicName, mentionCount))
		}
	}

	return strings.Join(lines, "\n")
}

// formatChannelContext formats channel messages as a chat log.
func formatChannelContext(messages []SessionMessage) string {
	if len(messages) == 0 {
		return ""
	}

	var lines []string
	for _, m := range messages {
		ts := formatMessageTimestamp(m.CreatedAt)
		prefix := ""
		if ts != "" {
			prefix = fmt.Sprintf("[%s] ", ts)
		}

		if m.Role == "assistant" {
			lines = append(lines, fmt.Sprintf("%sClara: %s", prefix, m.Content))
		} else {
			lines = append(lines, fmt.Sprintf("%s%s", prefix, m.Content))
		}
	}

	return "## Channel Context (recent messages in this channel)\n" + strings.Join(lines, "\n")
}

// formatMessageTimestamp formats a time.Time into a short timestamp string.
// Returns empty string for zero times.
func formatMessageTimestamp(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.UTC().Format("15:04")
}

// strPtr returns a pointer to s.
func strPtr(s string) *string {
	return &s
}
