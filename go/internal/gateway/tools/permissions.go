package tools

import (
	"os"
	"strings"
	"sync"
)

// RestrictedTools are tools that require the user to be trusted.
var RestrictedTools = map[string]bool{
	"execute_python":  true,
	"install_package": true,
	"run_shell":       true,
	"write_file":      true,
	"run_claude_code": true,
	"subagent_spawn":  true,
}

// SubagentBlocked are tools that subagents may never call.
var SubagentBlocked = map[string]bool{
	"subagent_spawn":  true,
	"subagent_kill":   true,
	"subagent_steer":  true,
	"run_shell":       true,
	"execute_python":  true,
	"run_claude_code": true,
}

// Permissions controls which users can execute which tools.
type Permissions struct {
	trustedUsers map[string]bool
	userDeny     map[string]map[string]bool // userID -> toolName -> denied
	mu           sync.RWMutex
}

// NewPermissions creates a Permissions instance, reading TRUSTED_USER_IDS
// from the environment (comma-separated).
func NewPermissions() *Permissions {
	p := &Permissions{
		trustedUsers: make(map[string]bool),
		userDeny:     make(map[string]map[string]bool),
	}

	if ids := os.Getenv("TRUSTED_USER_IDS"); ids != "" {
		for _, id := range strings.Split(ids, ",") {
			id = strings.TrimSpace(id)
			if id != "" {
				p.trustedUsers[id] = true
			}
		}
	}

	return p
}

// CanExecute checks whether userID is allowed to execute toolName.
// If isSubagent is true, SubagentBlocked tools are denied regardless of trust.
func (p *Permissions) CanExecute(toolName, userID string, isSubagent bool) bool {
	p.mu.RLock()
	defer p.mu.RUnlock()

	// Subagent-blocked tools are never allowed for subagents.
	if isSubagent && SubagentBlocked[toolName] {
		return false
	}

	// Per-user deny list.
	if denied, ok := p.userDeny[userID]; ok && denied[toolName] {
		return false
	}

	// Restricted tools require trusted user.
	if RestrictedTools[toolName] {
		return p.trustedUsers[userID]
	}

	// Non-restricted tools are allowed for everyone.
	return true
}

// DenyTool adds a tool to a user's deny list.
func (p *Permissions) DenyTool(userID, toolName string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.userDeny[userID] == nil {
		p.userDeny[userID] = make(map[string]bool)
	}
	p.userDeny[userID][toolName] = true
}
