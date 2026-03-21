package mcp

// Tool represents an MCP tool discovered from a server.
type Tool struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"input_schema"`
}

// LocalServerConfig for local MCP servers (stdio transport).
type LocalServerConfig struct {
	Name    string            `json:"name"`
	Command string            `json:"command"`
	Args    []string          `json:"args"`
	Env     map[string]string `json:"env,omitempty"`
	Enabled bool              `json:"enabled"`
	CWD     string            `json:"cwd,omitempty"`
}

// RemoteServerConfig for remote MCP servers (HTTP transport).
type RemoteServerConfig struct {
	Name      string            `json:"name"`
	ServerURL string            `json:"server_url"`
	Headers   map[string]string `json:"headers,omitempty"`
	Enabled   bool              `json:"enabled"`
}
