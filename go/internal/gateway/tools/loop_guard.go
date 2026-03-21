package tools

import (
	"encoding/json"
	"sync"
)

// LoopAction indicates whether a repeated tool call should be allowed.
type LoopAction int

const (
	// LoopAllow means the call is fine to proceed.
	LoopAllow LoopAction = iota
	// LoopWarn means the call is repeated but still allowed.
	LoopWarn
	// LoopStop means the call has been repeated too many times and must be blocked.
	LoopStop
)

const (
	loopWarnThreshold = 10
	loopStopThreshold = 30
)

type callRecord struct {
	Name string
	Args string // JSON-serialized args for comparison
}

// LoopGuard detects repeated identical tool calls.
type LoopGuard struct {
	history []callRecord
	mu      sync.Mutex
}

// NewLoopGuard creates a new LoopGuard.
func NewLoopGuard() *LoopGuard {
	return &LoopGuard{}
}

// Check examines whether the proposed call is a repeated identical call.
// It counts consecutive identical calls at the tail of the history.
func (g *LoopGuard) Check(name string, args map[string]any) LoopAction {
	g.mu.Lock()
	defer g.mu.Unlock()

	serialized := serializeArgs(args)
	current := callRecord{Name: name, Args: serialized}

	// Count consecutive identical calls from the end of history.
	count := 0
	for i := len(g.history) - 1; i >= 0; i-- {
		if g.history[i] == current {
			count++
		} else {
			break
		}
	}

	// Append the current call to history (before returning action).
	g.history = append(g.history, current)

	// count is how many previous identical calls exist; this is call count+1.
	if count >= loopStopThreshold {
		return LoopStop
	}
	if count >= loopWarnThreshold {
		return LoopWarn
	}
	return LoopAllow
}

// RecordResult is a no-op hook for future use (e.g., detecting identical results).
func (g *LoopGuard) RecordResult(name string, args map[string]any, result string) {
	// Currently unused; reserved for result-based loop detection.
}

func serializeArgs(args map[string]any) string {
	if args == nil {
		return "{}"
	}
	b, err := json.Marshal(args)
	if err != nil {
		return "{}"
	}
	return string(b)
}
