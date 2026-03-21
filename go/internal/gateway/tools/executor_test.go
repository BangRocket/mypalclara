package tools

import (
	"context"
	"fmt"
	"strings"
	"testing"
)

func TestExecutorRegisterAndExecute(t *testing.T) {
	exec := NewExecutor()
	exec.Register("greet", func(ctx context.Context, args map[string]any, userID string) (string, error) {
		name, _ := args["name"].(string)
		return fmt.Sprintf("Hello, %s!", name), nil
	})

	result, err := exec.Execute(context.Background(), "greet", map[string]any{"name": "Clara"}, "user-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Hello, Clara!" {
		t.Errorf("expected %q, got %q", "Hello, Clara!", result)
	}
}

func TestExecutorUnknownTool(t *testing.T) {
	exec := NewExecutor()
	_, err := exec.Execute(context.Background(), "nonexistent", nil, "user-1")
	if err == nil {
		t.Fatal("expected error for unknown tool")
	}
	if !strings.Contains(err.Error(), "unknown tool") {
		t.Errorf("expected 'unknown tool' error, got: %v", err)
	}
}

func TestPermissionsRestricted(t *testing.T) {
	p := &Permissions{
		trustedUsers: map[string]bool{},
		userDeny:     map[string]map[string]bool{},
	}

	// Untrusted user cannot run restricted tool.
	if p.CanExecute("execute_python", "untrusted-user", false) {
		t.Error("expected untrusted user to be denied restricted tool")
	}

	// Untrusted user can run non-restricted tool.
	if !p.CanExecute("search_memory", "untrusted-user", false) {
		t.Error("expected untrusted user to be allowed non-restricted tool")
	}
}

func TestPermissionsTrustedUser(t *testing.T) {
	p := &Permissions{
		trustedUsers: map[string]bool{"trusted-1": true},
		userDeny:     map[string]map[string]bool{},
	}

	// Trusted user can run restricted tool.
	if !p.CanExecute("execute_python", "trusted-1", false) {
		t.Error("expected trusted user to be allowed restricted tool")
	}

	// Trusted user can also run non-restricted tool.
	if !p.CanExecute("search_memory", "trusted-1", false) {
		t.Error("expected trusted user to be allowed non-restricted tool")
	}
}

func TestPermissionsSubagentBlocked(t *testing.T) {
	p := &Permissions{
		trustedUsers: map[string]bool{"trusted-1": true},
		userDeny:     map[string]map[string]bool{},
	}

	// Even trusted user as subagent cannot run subagent-blocked tool.
	if p.CanExecute("subagent_spawn", "trusted-1", true) {
		t.Error("expected subagent to be denied subagent-blocked tool")
	}

	// Non-blocked tool is fine for subagent (if not restricted, or user is trusted).
	if !p.CanExecute("search_memory", "trusted-1", true) {
		t.Error("expected subagent to be allowed non-blocked tool")
	}
}

func TestCircuitBreakerTrips(t *testing.T) {
	cb := NewCircuitBreaker()

	// Should be open initially.
	if ok, _ := cb.CanExecute("flaky_tool"); !ok {
		t.Fatal("expected circuit to be closed initially")
	}

	// Record failures up to threshold (5).
	for i := 0; i < 5; i++ {
		cb.RecordFailure("flaky_tool")
	}

	// Now circuit should be open.
	ok, reason := cb.CanExecute("flaky_tool")
	if ok {
		t.Fatal("expected circuit to be open after threshold failures")
	}
	if !strings.Contains(reason, "too many failures") {
		t.Errorf("expected reason about failures, got: %q", reason)
	}

	// Other tools should be unaffected.
	if ok2, _ := cb.CanExecute("other_tool"); !ok2 {
		t.Error("expected other tool's circuit to be closed")
	}

	// After recording success, circuit resets (simulate cooldown passed by clearing).
	cb.mu.Lock()
	delete(cb.openUntil, "flaky_tool")
	cb.mu.Unlock()
	cb.RecordSuccess("flaky_tool")

	if ok3, _ := cb.CanExecute("flaky_tool"); !ok3 {
		t.Error("expected circuit to be closed after success")
	}
}

func TestLoopGuardStopsRepeats(t *testing.T) {
	g := NewLoopGuard()
	args := map[string]any{"query": "same thing"}

	// First 10 calls should be LoopAllow.
	for i := 0; i < 10; i++ {
		action := g.Check("search", args)
		if action != LoopAllow {
			t.Fatalf("call %d: expected LoopAllow, got %d", i, action)
		}
	}

	// Calls 11-30 should be LoopWarn.
	for i := 10; i < 30; i++ {
		action := g.Check("search", args)
		if action != LoopWarn {
			t.Fatalf("call %d: expected LoopWarn, got %d", i, action)
		}
	}

	// Call 31 should be LoopStop.
	action := g.Check("search", args)
	if action != LoopStop {
		t.Fatalf("call 31: expected LoopStop, got %d", action)
	}

	// A different call resets the consecutive counter.
	action2 := g.Check("other_tool", map[string]any{"x": 1})
	if action2 != LoopAllow {
		t.Fatalf("different tool: expected LoopAllow, got %d", action2)
	}
}

func TestResultGuardCaps(t *testing.T) {
	g := NewResultGuard(100)

	// Short output is untouched.
	short := "hello"
	if got := g.Cap(short); got != short {
		t.Errorf("expected %q, got %q", short, got)
	}

	// Long output is truncated.
	long := strings.Repeat("x", 200)
	capped := g.Cap(long)
	if !strings.HasSuffix(capped, "[truncated]") {
		t.Error("expected truncation marker")
	}
	// Should be 100 chars of content + "\n[truncated]"
	if !strings.HasPrefix(capped, strings.Repeat("x", 100)) {
		t.Error("expected first 100 chars preserved")
	}

	// Error messages are never truncated.
	errMsg := "Error: " + strings.Repeat("y", 200)
	if got := g.Cap(errMsg); got != errMsg {
		t.Error("expected error message to pass through untouched")
	}
}
