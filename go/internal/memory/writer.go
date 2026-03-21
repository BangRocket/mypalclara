package memory

import (
	"context"
	"fmt"
)

// Writer extracts and stores memories from conversations.
type Writer struct {
	rook *Rook
}

// NewWriter creates a Writer backed by the given Rook instance.
func NewWriter(rook *Rook) *Writer {
	return &Writer{rook: rook}
}

// WriteOptions configures an AddFromConversation call.
type WriteOptions struct {
	UserID         string
	ProjectID      string
	RecentMessages []SessionMessage
	UserMessage    string
	AssistantReply string
	IsDM           bool
}

// AddFromConversation extracts memories from a user-assistant exchange
// and stores them in Rook.
func (w *Writer) AddFromConversation(ctx context.Context, opts WriteOptions) error {
	// Build the message slice for Rook extraction.
	// Take the last MemoryContextSlice messages from recent history,
	// then append the current exchange.
	messages := buildExtractionMessages(opts)

	if len(messages) == 0 {
		return nil
	}

	// Determine memory type and visibility.
	memType := MemoryTypeUser
	visibility := "private"
	if opts.ProjectID != "" {
		memType = MemoryTypeProject
	}
	if !opts.IsDM {
		visibility = "public"
	}

	metadata := map[string]any{
		"type":       string(memType),
		"visibility": visibility,
	}
	if opts.ProjectID != "" {
		metadata["project_id"] = opts.ProjectID
	}

	_, err := w.rook.Add(ctx, messages, AddOptions{
		UserID:   opts.UserID,
		Metadata: metadata,
	})
	if err != nil {
		return fmt.Errorf("writer: add from conversation: %w", err)
	}

	return nil
}

// buildExtractionMessages constructs the message list for memory extraction.
// It takes the last MemoryContextSlice messages from recent history and appends
// the current user message and assistant reply.
func buildExtractionMessages(opts WriteOptions) []map[string]string {
	messages := make([]map[string]string, 0, MemoryContextSlice+2)

	// Include the tail of recent conversation history.
	recent := opts.RecentMessages
	if len(recent) > MemoryContextSlice {
		recent = recent[len(recent)-MemoryContextSlice:]
	}
	for _, msg := range recent {
		messages = append(messages, map[string]string{
			"role":    msg.Role,
			"content": msg.Content,
		})
	}

	// Append the current exchange.
	if opts.UserMessage != "" {
		messages = append(messages, map[string]string{
			"role":    "user",
			"content": opts.UserMessage,
		})
	}
	if opts.AssistantReply != "" {
		messages = append(messages, map[string]string{
			"role":    "assistant",
			"content": opts.AssistantReply,
		})
	}

	return messages
}
