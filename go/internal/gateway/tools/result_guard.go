package tools

import "strings"

// ResultGuard truncates tool output that exceeds a character limit.
type ResultGuard struct {
	maxChars int
}

// NewResultGuard creates a ResultGuard. If maxChars <= 0, defaults to 50000.
func NewResultGuard(maxChars int) *ResultGuard {
	if maxChars <= 0 {
		maxChars = 50000
	}
	return &ResultGuard{maxChars: maxChars}
}

// Cap truncates output if it exceeds maxChars, appending a truncation marker.
// Error messages (starting with "Error:") are never truncated.
func (g *ResultGuard) Cap(output string) string {
	if strings.HasPrefix(output, "Error:") {
		return output
	}
	if len(output) <= g.maxChars {
		return output
	}
	return output[:g.maxChars] + "\n[truncated]"
}
