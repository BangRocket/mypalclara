package sandbox

import (
	"context"
	"testing"
)

func TestManagerDefaults(t *testing.T) {
	m := NewManager()

	if m.image != "python:3.12-slim" {
		t.Errorf("expected default image python:3.12-slim, got %q", m.image)
	}
	if m.timeout != 900 {
		t.Errorf("expected default timeout 900, got %d", m.timeout)
	}
	// enabled depends on Docker availability; just verify it doesn't panic.
	_ = m.IsEnabled()
}

func TestHandleToolCallRouting(t *testing.T) {
	// Create a manager but don't require Docker to be running.
	m := &Manager{
		image:   "python:3.12-slim",
		timeout: 10,
		enabled: false,
	}
	ctx := context.Background()

	// execute_python should fail gracefully when Docker is not available.
	_, err := m.HandleToolCall(ctx, "test-user", "execute_python", map[string]any{
		"code": "print('hello')",
	})
	if err == nil {
		t.Fatal("expected error when Docker is not available")
	}
	if err.Error() != "docker is not available" {
		t.Errorf("unexpected error: %v", err)
	}

	// run_shell should fail gracefully when Docker is not available.
	_, err = m.HandleToolCall(ctx, "test-user", "run_shell", map[string]any{
		"command": "echo hello",
	})
	if err == nil {
		t.Fatal("expected error when Docker is not available")
	}

	// Unknown tool should return appropriate error.
	_, err = m.HandleToolCall(ctx, "test-user", "unknown_tool", nil)
	if err == nil {
		t.Fatal("expected error for unknown tool")
	}
	if err.Error() != `unknown sandbox tool: "unknown_tool"` {
		t.Errorf("unexpected error: %v", err)
	}

	// Missing required arguments.
	_, err = m.HandleToolCall(ctx, "test-user", "execute_python", map[string]any{})
	if err == nil {
		t.Fatal("expected error for missing code")
	}

	_, err = m.HandleToolCall(ctx, "test-user", "run_shell", map[string]any{})
	if err == nil {
		t.Fatal("expected error for missing command")
	}
}

func TestHandleToolCallWithDocker(t *testing.T) {
	m := NewManager()
	if !m.IsEnabled() {
		t.Skip("Docker not available, skipping integration test")
	}

	ctx := context.Background()
	result, err := m.HandleToolCall(ctx, "test-user", "execute_python", map[string]any{
		"code": "print('hello from sandbox')",
	})
	if err != nil {
		t.Fatalf("execute_python failed: %v", err)
	}
	if !result.Success {
		t.Fatalf("expected success, got error: %s", result.Error)
	}
	if result.Output == "" {
		t.Fatal("expected output from python execution")
	}
}
