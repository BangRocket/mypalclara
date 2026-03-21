package gateway

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAPIHealth(t *testing.T) {
	server := NewServer("127.0.0.1", 0, "")
	api := NewAPI("127.0.0.1", 0, server, nil)

	req := httptest.NewRequest(http.MethodGet, "/v1/health", nil)
	w := httptest.NewRecorder()

	api.mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var body map[string]any
	if err := json.NewDecoder(w.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if body["status"] != "ok" {
		t.Errorf("expected status %q, got %q", "ok", body["status"])
	}
	if _, ok := body["time"]; !ok {
		t.Error("expected 'time' field in response")
	}
}

func TestAPIStatus(t *testing.T) {
	server := NewServer("127.0.0.1", 0, "")
	api := NewAPI("127.0.0.1", 0, server, nil)

	req := httptest.NewRequest(http.MethodGet, "/v1/status", nil)
	w := httptest.NewRecorder()

	api.mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var body map[string]any
	if err := json.NewDecoder(w.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if body["status"] != "running" {
		t.Errorf("expected status %q, got %q", "running", body["status"])
	}
	if body["node_count"] != float64(0) {
		t.Errorf("expected node_count 0, got %v", body["node_count"])
	}
}

func TestAPIMessages_NoProcessor(t *testing.T) {
	server := NewServer("127.0.0.1", 0, "")
	api := NewAPI("127.0.0.1", 0, server, nil) // nil processor

	body := `{"content":"hello","user_id":"test-user"}`
	req := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	api.mux.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d", w.Code)
	}
}

func TestAPIMessages_EmptyContent(t *testing.T) {
	server := NewServer("127.0.0.1", 0, "")
	api := NewAPI("127.0.0.1", 0, server, nil)

	body := `{"content":"","user_id":"test-user"}`
	req := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	api.mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}

func TestAPIMessages_InvalidJSON(t *testing.T) {
	server := NewServer("127.0.0.1", 0, "")
	api := NewAPI("127.0.0.1", 0, server, nil)

	req := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader("not json"))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	api.mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}
