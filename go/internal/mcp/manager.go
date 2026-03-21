package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

const toolNameSep = "__"

// Manager manages all MCP server connections.
type Manager struct {
	locals  map[string]*LocalClient
	remotes map[string]*RemoteClient
	mu      sync.RWMutex
}

// NewManager creates a new MCP manager.
func NewManager() *Manager {
	return &Manager{
		locals:  make(map[string]*LocalClient),
		remotes: make(map[string]*RemoteClient),
	}
}

// Initialize loads and connects all enabled servers from the config directory.
// It looks for JSON files in the MCP_SERVERS_DIR (default: .mcp_servers).
func (m *Manager) Initialize(ctx context.Context) error {
	dir := os.Getenv("MCP_SERVERS_DIR")
	if dir == "" {
		dir = ".mcp_servers"
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // No config directory is fine.
		}
		return fmt.Errorf("mcp: read config dir: %w", err)
	}

	var errs []string
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			errs = append(errs, fmt.Sprintf("read %s: %v", entry.Name(), err))
			continue
		}

		if err := m.loadConfig(ctx, data); err != nil {
			errs = append(errs, fmt.Sprintf("load %s: %v", entry.Name(), err))
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("mcp: initialization errors:\n  %s", strings.Join(errs, "\n  "))
	}
	return nil
}

// loadConfig parses a config file and connects the server.
func (m *Manager) loadConfig(ctx context.Context, data []byte) error {
	// Try local config first.
	var local LocalServerConfig
	if err := json.Unmarshal(data, &local); err == nil && local.Command != "" {
		if !local.Enabled {
			return nil
		}
		return m.AddLocal(ctx, local)
	}

	// Try remote config.
	var remote RemoteServerConfig
	if err := json.Unmarshal(data, &remote); err == nil && remote.ServerURL != "" {
		if !remote.Enabled {
			return nil
		}
		return m.AddRemote(ctx, remote)
	}

	return fmt.Errorf("unrecognized config format")
}

// AddLocal adds and connects a local MCP server.
func (m *Manager) AddLocal(ctx context.Context, config LocalServerConfig) error {
	client := NewLocalClient(config)
	if err := client.Connect(ctx); err != nil {
		return err
	}

	m.mu.Lock()
	m.locals[config.Name] = client
	m.mu.Unlock()
	return nil
}

// AddRemote adds and connects a remote MCP server.
func (m *Manager) AddRemote(ctx context.Context, config RemoteServerConfig) error {
	client := NewRemoteClient(config)
	if err := client.Connect(ctx); err != nil {
		return err
	}

	m.mu.Lock()
	m.remotes[config.Name] = client
	m.mu.Unlock()
	return nil
}

// GetAllTools returns tools from all connected servers with namespaced names.
// Tool names are formatted as serverName__toolName (double underscore).
func (m *Manager) GetAllTools() []Tool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var all []Tool
	for serverName, client := range m.locals {
		for _, t := range client.ListTools() {
			all = append(all, Tool{
				Name:        serverName + toolNameSep + t.Name,
				Description: t.Description,
				InputSchema: t.InputSchema,
			})
		}
	}
	for serverName, client := range m.remotes {
		for _, t := range client.ListTools() {
			all = append(all, Tool{
				Name:        serverName + toolNameSep + t.Name,
				Description: t.Description,
				InputSchema: t.InputSchema,
			})
		}
	}
	return all
}

// CallTool routes a tool call to the correct server.
func (m *Manager) CallTool(ctx context.Context, toolName string, args map[string]any) (string, error) {
	serverName, rawToolName, ok := parseToolName(toolName)
	if !ok {
		return "", fmt.Errorf("mcp: invalid tool name %q (expected server__tool)", toolName)
	}

	m.mu.RLock()
	defer m.mu.RUnlock()

	if client, exists := m.locals[serverName]; exists {
		return client.CallTool(ctx, rawToolName, args)
	}
	if client, exists := m.remotes[serverName]; exists {
		return client.CallTool(ctx, rawToolName, args)
	}

	return "", fmt.Errorf("mcp: unknown server %q", serverName)
}

// IsToolMCP checks if a tool name belongs to an MCP server.
func (m *Manager) IsToolMCP(toolName string) bool {
	_, _, ok := parseToolName(toolName)
	return ok
}

// Shutdown disconnects all servers.
func (m *Manager) Shutdown(_ context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	var errs []string
	for name, client := range m.locals {
		if err := client.Disconnect(); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", name, err))
		}
	}
	for name, client := range m.remotes {
		if err := client.Disconnect(); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", name, err))
		}
	}

	m.locals = make(map[string]*LocalClient)
	m.remotes = make(map[string]*RemoteClient)

	if len(errs) > 0 {
		return fmt.Errorf("mcp: shutdown errors: %s", strings.Join(errs, "; "))
	}
	return nil
}

// parseToolName splits a namespaced tool name into server and tool parts.
func parseToolName(name string) (server, tool string, ok bool) {
	idx := strings.Index(name, toolNameSep)
	if idx < 0 {
		return "", "", false
	}
	server = name[:idx]
	tool = name[idx+len(toolNameSep):]
	if server == "" || tool == "" {
		return "", "", false
	}
	return server, tool, true
}
