package tools

import (
	"context"
	"fmt"
	"sync"
)

// Handler is a function that handles a specific tool.
type Handler func(ctx context.Context, args map[string]any, userID string) (string, error)

// Executor routes and executes tool calls.
type Executor struct {
	handlers    map[string]Handler
	permissions *Permissions
	breaker     *CircuitBreaker
	loopGuard   *LoopGuard
	resultGuard *ResultGuard
	mu          sync.RWMutex
}

// NewExecutor creates an Executor with default guards.
func NewExecutor() *Executor {
	return &Executor{
		handlers:    make(map[string]Handler),
		permissions: NewPermissions(),
		breaker:     NewCircuitBreaker(),
		loopGuard:   NewLoopGuard(),
		resultGuard: NewResultGuard(50000),
	}
}

// Register adds a tool handler.
func (e *Executor) Register(name string, handler Handler) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.handlers[name] = handler
}

// Execute routes and executes a tool call with all guards.
func (e *Executor) Execute(ctx context.Context, toolName string, args map[string]any, userID string) (string, error) {
	// 1. Permission check.
	if !e.permissions.CanExecute(toolName, userID, false) {
		return "", fmt.Errorf("permission denied: user %q cannot execute tool %q", userID, toolName)
	}

	// 2. Circuit breaker check.
	if ok, reason := e.breaker.CanExecute(toolName); !ok {
		return "", fmt.Errorf("circuit open for tool %q: %s", toolName, reason)
	}

	// 3. Loop guard check.
	action := e.loopGuard.Check(toolName, args)
	switch action {
	case LoopStop:
		return "", fmt.Errorf("loop detected: tool %q called too many times with identical arguments", toolName)
	case LoopWarn:
		// Allow but the caller could log this; we proceed.
	}

	// 4. Route to handler.
	e.mu.RLock()
	handler, ok := e.handlers[toolName]
	e.mu.RUnlock()
	if !ok {
		return "", fmt.Errorf("unknown tool: %q", toolName)
	}

	result, err := handler(ctx, args, userID)
	if err != nil {
		e.breaker.RecordFailure(toolName)
		return "", err
	}

	// 5. Record success and cap result.
	e.breaker.RecordSuccess(toolName)
	e.loopGuard.RecordResult(toolName, args, result)

	return e.resultGuard.Cap(result), nil
}
