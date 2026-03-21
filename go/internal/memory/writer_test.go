package memory

import (
	"context"
	"testing"
	"time"
)

func TestAddFromConversation(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{
		response: "Joshua prefers dark mode\nJoshua is a Go developer",
	}
	rook := NewRook(vs, emb, provider, nil)
	writer := NewWriter(rook)

	recent := []SessionMessage{
		{ID: 1, Role: "user", Content: "I like dark mode.", CreatedAt: time.Now()},
		{ID: 2, Role: "assistant", Content: "Noted!", CreatedAt: time.Now()},
	}

	err := writer.AddFromConversation(context.Background(), WriteOptions{
		UserID:         "user-1",
		RecentMessages: recent,
		UserMessage:    "I'm also a Go developer.",
		AssistantReply: "That's great!",
		IsDM:           true,
	})
	if err != nil {
		t.Fatalf("AddFromConversation failed: %v", err)
	}

	// Rook should have stored 2 extracted facts.
	if len(vs.data) != 2 {
		t.Errorf("expected 2 items in vector store, got %d", len(vs.data))
	}

	// Verify metadata on stored items.
	for _, res := range vs.data {
		uid, _ := res.Payload["user_id"].(string)
		if uid != "user-1" {
			t.Errorf("expected user_id 'user-1', got %q", uid)
		}
		vis, _ := res.Payload["visibility"].(string)
		if vis != "private" {
			t.Errorf("expected visibility 'private' for DM, got %q", vis)
		}
		memType, _ := res.Payload["type"].(string)
		if memType != "user" {
			t.Errorf("expected type 'user', got %q", memType)
		}
	}
}

func TestAddFromConversationPublic(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{
		response: "Channel fact one",
	}
	rook := NewRook(vs, emb, provider, nil)
	writer := NewWriter(rook)

	err := writer.AddFromConversation(context.Background(), WriteOptions{
		UserID:         "user-1",
		UserMessage:    "Hello channel!",
		AssistantReply: "Hi there!",
		IsDM:           false, // Group channel — should be public.
	})
	if err != nil {
		t.Fatalf("AddFromConversation failed: %v", err)
	}

	for _, res := range vs.data {
		vis, _ := res.Payload["visibility"].(string)
		if vis != "public" {
			t.Errorf("expected visibility 'public' for non-DM, got %q", vis)
		}
	}
}

func TestAddFromConversationWithProject(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{
		response: "Project uses PostgreSQL",
	}
	rook := NewRook(vs, emb, provider, nil)
	writer := NewWriter(rook)

	err := writer.AddFromConversation(context.Background(), WriteOptions{
		UserID:         "user-1",
		ProjectID:      "proj-123",
		UserMessage:    "We use PostgreSQL.",
		AssistantReply: "Got it.",
		IsDM:           true,
	})
	if err != nil {
		t.Fatalf("AddFromConversation failed: %v", err)
	}

	for _, res := range vs.data {
		memType, _ := res.Payload["type"].(string)
		if memType != "project" {
			t.Errorf("expected type 'project' when ProjectID set, got %q", memType)
		}
		pid, _ := res.Payload["project_id"].(string)
		if pid != "proj-123" {
			t.Errorf("expected project_id 'proj-123', got %q", pid)
		}
	}
}

func TestAddFromConversationEmpty(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{response: "NONE"}
	rook := NewRook(vs, emb, provider, nil)
	writer := NewWriter(rook)

	// No user message and no assistant reply — should skip entirely.
	err := writer.AddFromConversation(context.Background(), WriteOptions{
		UserID: "user-1",
	})
	if err != nil {
		t.Fatalf("AddFromConversation failed: %v", err)
	}

	if len(vs.data) != 0 {
		t.Errorf("expected 0 items for empty conversation, got %d", len(vs.data))
	}
}

func TestAddFromConversationSlicing(t *testing.T) {
	vs := newMockVectorStore()
	emb := newMockEmbedder()
	provider := &mockProvider{
		response: "A fact",
	}
	rook := NewRook(vs, emb, provider, nil)
	writer := NewWriter(rook)

	// Create more recent messages than MemoryContextSlice (4).
	recent := make([]SessionMessage, 10)
	for i := range recent {
		recent[i] = SessionMessage{
			ID:      i + 1,
			Role:    "user",
			Content: "message " + string(rune('A'+i)),
		}
	}

	err := writer.AddFromConversation(context.Background(), WriteOptions{
		UserID:         "user-1",
		RecentMessages: recent,
		UserMessage:    "current message",
		AssistantReply: "reply",
		IsDM:           true,
	})
	if err != nil {
		t.Fatalf("AddFromConversation failed: %v", err)
	}

	// Verify that buildExtractionMessages only takes last 4 + current exchange.
	msgs := buildExtractionMessages(WriteOptions{
		UserID:         "user-1",
		RecentMessages: recent,
		UserMessage:    "current message",
		AssistantReply: "reply",
	})

	// MemoryContextSlice(4) + user(1) + assistant(1) = 6
	if len(msgs) != 6 {
		t.Errorf("expected 6 extraction messages, got %d", len(msgs))
	}
}
