package vector

import (
	"testing"

	"github.com/qdrant/go-client/qdrant"
)

// TestQdrantStoreImplementsInterface verifies that QdrantStore satisfies the
// VectorStore interface at compile time.
func TestQdrantStoreImplementsInterface(t *testing.T) {
	// Compile-time check: *QdrantStore must implement VectorStore.
	var _ VectorStore = (*QdrantStore)(nil)
}

// TestSearchResultFields verifies that SearchResult fields are populated
// correctly from construction.
func TestSearchResultFields(t *testing.T) {
	result := SearchResult{
		ID:    "test-uuid-123",
		Score: 0.95,
		Payload: map[string]any{
			"user_id": "user-1",
			"text":    "hello world",
		},
		Vector: []float32{0.1, 0.2, 0.3},
	}

	if result.ID != "test-uuid-123" {
		t.Errorf("expected ID %q, got %q", "test-uuid-123", result.ID)
	}
	if result.Score != 0.95 {
		t.Errorf("expected Score 0.95, got %f", result.Score)
	}
	if result.Payload["user_id"] != "user-1" {
		t.Errorf("expected Payload[user_id] %q, got %v", "user-1", result.Payload["user_id"])
	}
	if len(result.Vector) != 3 {
		t.Errorf("expected Vector length 3, got %d", len(result.Vector))
	}
}

// TestFilterConstruction verifies that buildQdrantFilter correctly translates
// Filter structs into Qdrant filter conditions.
func TestFilterConstruction(t *testing.T) {
	t.Run("nil filter returns nil", func(t *testing.T) {
		f := buildQdrantFilter(nil)
		if f != nil {
			t.Error("expected nil filter for nil input")
		}
	})

	t.Run("empty filter returns nil", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{})
		if f != nil {
			t.Error("expected nil filter for empty Filter")
		}
	})

	t.Run("user_id only", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{UserID: "user-42"})
		if f == nil {
			t.Fatal("expected non-nil filter")
		}
		if len(f.Must) != 1 {
			t.Fatalf("expected 1 must condition, got %d", len(f.Must))
		}
		cond := f.Must[0]
		field := cond.GetField()
		if field == nil {
			t.Fatal("expected field condition")
		}
		if field.Key != "user_id" {
			t.Errorf("expected key %q, got %q", "user_id", field.Key)
		}
		if field.Match.GetKeyword() != "user-42" {
			t.Errorf("expected keyword %q, got %q", "user-42", field.Match.GetKeyword())
		}
	})

	t.Run("user_id and agent_id", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{UserID: "u1", AgentID: "a1"})
		if f == nil {
			t.Fatal("expected non-nil filter")
		}
		if len(f.Must) != 2 {
			t.Fatalf("expected 2 must conditions, got %d", len(f.Must))
		}

		keys := make(map[string]string)
		for _, c := range f.Must {
			field := c.GetField()
			if field != nil {
				keys[field.Key] = field.Match.GetKeyword()
			}
		}
		if keys["user_id"] != "u1" {
			t.Errorf("expected user_id=u1, got %q", keys["user_id"])
		}
		if keys["agent_id"] != "a1" {
			t.Errorf("expected agent_id=a1, got %q", keys["agent_id"])
		}
	})

	t.Run("custom string filter", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{
			Filters: map[string]any{
				"category": "memory",
			},
		})
		if f == nil {
			t.Fatal("expected non-nil filter")
		}
		if len(f.Must) != 1 {
			t.Fatalf("expected 1 must condition, got %d", len(f.Must))
		}
		field := f.Must[0].GetField()
		if field.Key != "category" {
			t.Errorf("expected key %q, got %q", "category", field.Key)
		}
		if field.Match.GetKeyword() != "memory" {
			t.Errorf("expected keyword %q, got %q", "memory", field.Match.GetKeyword())
		}
	})

	t.Run("custom int filter", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{
			Filters: map[string]any{
				"priority": int64(5),
			},
		})
		if f == nil {
			t.Fatal("expected non-nil filter")
		}
		field := f.Must[0].GetField()
		if field.Key != "priority" {
			t.Errorf("expected key %q, got %q", "priority", field.Key)
		}
		if field.Match.GetInteger() != 5 {
			t.Errorf("expected integer 5, got %d", field.Match.GetInteger())
		}
	})

	t.Run("custom bool filter", func(t *testing.T) {
		f := buildQdrantFilter(&Filter{
			Filters: map[string]any{
				"active": true,
			},
		})
		if f == nil {
			t.Fatal("expected non-nil filter")
		}
		field := f.Must[0].GetField()
		if field.Key != "active" {
			t.Errorf("expected key %q, got %q", "active", field.Key)
		}
		if !field.Match.GetBoolean() {
			t.Error("expected boolean true")
		}
	})
}

// TestExtractPointID verifies UUID and numeric ID extraction.
func TestExtractPointID(t *testing.T) {
	t.Run("uuid", func(t *testing.T) {
		id := extractPointID(qdrant.NewIDUUID("abc-123"))
		if id != "abc-123" {
			t.Errorf("expected %q, got %q", "abc-123", id)
		}
	})

	t.Run("numeric", func(t *testing.T) {
		id := extractPointID(qdrant.NewIDNum(42))
		if id != "42" {
			t.Errorf("expected %q, got %q", "42", id)
		}
	})

	t.Run("nil", func(t *testing.T) {
		id := extractPointID(nil)
		if id != "" {
			t.Errorf("expected empty string, got %q", id)
		}
	})
}

// TestExtractPayload verifies payload map conversion from Qdrant values.
func TestExtractPayload(t *testing.T) {
	t.Run("nil payload", func(t *testing.T) {
		p := extractPayload(nil)
		if p != nil {
			t.Error("expected nil for nil input")
		}
	})

	t.Run("mixed types", func(t *testing.T) {
		input := map[string]*qdrant.Value{
			"str":  qdrant.NewValueString("hello"),
			"num":  qdrant.NewValueInt(42),
			"flag": qdrant.NewValueBool(true),
			"pi":   qdrant.NewValueDouble(3.14),
		}
		p := extractPayload(input)

		if p["str"] != "hello" {
			t.Errorf("expected str=hello, got %v", p["str"])
		}
		if p["num"] != int64(42) {
			t.Errorf("expected num=42, got %v", p["num"])
		}
		if p["flag"] != true {
			t.Errorf("expected flag=true, got %v", p["flag"])
		}
		if p["pi"] != 3.14 {
			t.Errorf("expected pi=3.14, got %v", p["pi"])
		}
	})
}
