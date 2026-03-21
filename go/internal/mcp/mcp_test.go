package mcp

import (
	"encoding/json"
	"testing"
)

func TestToolNamespacing(t *testing.T) {
	tests := []struct {
		server string
		tool   string
		want   string
	}{
		{"weather", "get_forecast", "weather__get_forecast"},
		{"my-server", "do_thing", "my-server__do_thing"},
		{"srv", "nested__name", "srv__nested__name"},
	}

	for _, tt := range tests {
		got := tt.server + toolNameSep + tt.tool
		if got != tt.want {
			t.Errorf("namespace(%q, %q) = %q, want %q", tt.server, tt.tool, got, tt.want)
		}

		// Verify round-trip through parseToolName.
		server, tool, ok := parseToolName(got)
		if !ok {
			t.Errorf("parseToolName(%q) returned not ok", got)
			continue
		}
		if server != tt.server {
			t.Errorf("parseToolName(%q) server = %q, want %q", got, server, tt.server)
		}
		if tool != tt.tool {
			t.Errorf("parseToolName(%q) tool = %q, want %q", got, tool, tt.tool)
		}
	}
}

func TestManagerIsToolMCP(t *testing.T) {
	m := NewManager()

	mcpTools := []string{
		"weather__get_forecast",
		"github__create_issue",
		"server__tool",
	}
	for _, name := range mcpTools {
		if !m.IsToolMCP(name) {
			t.Errorf("IsToolMCP(%q) = false, want true", name)
		}
	}

	nonMCPTools := []string{
		"web_search",
		"run_code",
		"simple",
		"",
		"__leading",
		"trailing__",
	}
	for _, name := range nonMCPTools {
		if m.IsToolMCP(name) {
			t.Errorf("IsToolMCP(%q) = true, want false", name)
		}
	}
}

func TestLocalServerConfigParsing(t *testing.T) {
	raw := `{
		"name": "test-server",
		"command": "node",
		"args": ["server.js", "--port", "3000"],
		"env": {"NODE_ENV": "production"},
		"enabled": true,
		"cwd": "/opt/mcp"
	}`

	var config LocalServerConfig
	if err := json.Unmarshal([]byte(raw), &config); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if config.Name != "test-server" {
		t.Errorf("Name = %q, want %q", config.Name, "test-server")
	}
	if config.Command != "node" {
		t.Errorf("Command = %q, want %q", config.Command, "node")
	}
	if len(config.Args) != 3 || config.Args[0] != "server.js" {
		t.Errorf("Args = %v, want [server.js --port 3000]", config.Args)
	}
	if config.Env["NODE_ENV"] != "production" {
		t.Errorf("Env[NODE_ENV] = %q, want %q", config.Env["NODE_ENV"], "production")
	}
	if !config.Enabled {
		t.Error("Enabled = false, want true")
	}
	if config.CWD != "/opt/mcp" {
		t.Errorf("CWD = %q, want %q", config.CWD, "/opt/mcp")
	}
}

func TestManagerGetAllToolsEmpty(t *testing.T) {
	m := NewManager()
	tools := m.GetAllTools()
	if tools != nil {
		t.Errorf("GetAllTools() = %v, want nil", tools)
	}
}

func TestRemoteServerConfigParsing(t *testing.T) {
	raw := `{
		"name": "remote-mcp",
		"server_url": "https://mcp.example.com/api",
		"headers": {"Authorization": "Bearer token123"},
		"enabled": true
	}`

	var config RemoteServerConfig
	if err := json.Unmarshal([]byte(raw), &config); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if config.Name != "remote-mcp" {
		t.Errorf("Name = %q, want %q", config.Name, "remote-mcp")
	}
	if config.ServerURL != "https://mcp.example.com/api" {
		t.Errorf("ServerURL = %q, want %q", config.ServerURL, "https://mcp.example.com/api")
	}
	if config.Headers["Authorization"] != "Bearer token123" {
		t.Errorf("Headers[Authorization] = %q, want %q", config.Headers["Authorization"], "Bearer token123")
	}
	if !config.Enabled {
		t.Error("Enabled = false, want true")
	}
}

func TestParseToolNameEdgeCases(t *testing.T) {
	tests := []struct {
		input      string
		wantServer string
		wantTool   string
		wantOk     bool
	}{
		{"server__tool", "server", "tool", true},
		{"a__b", "a", "b", true},
		{"srv__nested__name", "srv", "nested__name", true},
		{"no_separator", "", "", false},
		{"__leading", "", "", false},
		{"trailing__", "", "", false},
		{"", "", "", false},
	}

	for _, tt := range tests {
		server, tool, ok := parseToolName(tt.input)
		if ok != tt.wantOk {
			t.Errorf("parseToolName(%q) ok = %v, want %v", tt.input, ok, tt.wantOk)
			continue
		}
		if ok {
			if server != tt.wantServer {
				t.Errorf("parseToolName(%q) server = %q, want %q", tt.input, server, tt.wantServer)
			}
			if tool != tt.wantTool {
				t.Errorf("parseToolName(%q) tool = %q, want %q", tt.input, tool, tt.wantTool)
			}
		}
	}
}
