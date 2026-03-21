package tools

import (
	"fmt"
	"sync"
	"time"
)

// CircuitBreaker tracks consecutive failures per tool and temporarily
// disables tools that fail too often.
type CircuitBreaker struct {
	failures  map[string]int
	openUntil map[string]time.Time
	threshold int           // consecutive failures before opening (default 5)
	cooldown  time.Duration // how long the circuit stays open (default 30s)
	mu        sync.Mutex
}

// NewCircuitBreaker creates a CircuitBreaker with default settings.
func NewCircuitBreaker() *CircuitBreaker {
	return &CircuitBreaker{
		failures:  make(map[string]int),
		openUntil: make(map[string]time.Time),
		threshold: 5,
		cooldown:  30 * time.Second,
	}
}

// CanExecute returns whether the tool's circuit is closed (ok to call).
// If the circuit is open, it returns false and a reason string.
func (cb *CircuitBreaker) CanExecute(toolName string) (bool, string) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if until, ok := cb.openUntil[toolName]; ok && time.Now().Before(until) {
		remaining := time.Until(until).Round(time.Second)
		return false, fmt.Sprintf("too many failures, retry after %s", remaining)
	}

	// If cooldown has passed, clean up.
	delete(cb.openUntil, toolName)
	return true, ""
}

// RecordSuccess resets the failure counter for a tool.
func (cb *CircuitBreaker) RecordSuccess(toolName string) {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	delete(cb.failures, toolName)
	delete(cb.openUntil, toolName)
}

// RecordFailure increments the failure counter and opens the circuit
// if the threshold is reached.
func (cb *CircuitBreaker) RecordFailure(toolName string) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.failures[toolName]++
	if cb.failures[toolName] >= cb.threshold {
		cb.openUntil[toolName] = time.Now().Add(cb.cooldown)
		cb.failures[toolName] = 0 // reset for next cycle
	}
}
