package cli

import (
	"os"
	"testing"
)

func TestThemeAutoDetect(t *testing.T) {
	// Default (no COLORFGBG set) should be dark.
	os.Unsetenv("COLORFGBG")
	theme := NewTheme()
	if !theme.Dark {
		t.Error("expected dark theme by default when COLORFGBG is unset")
	}
}

func TestThemeAutoDetectLight(t *testing.T) {
	os.Setenv("COLORFGBG", "0;15")
	defer os.Unsetenv("COLORFGBG")

	theme := NewTheme()
	if theme.Dark {
		t.Error("expected light theme when COLORFGBG indicates light background (15)")
	}
}

func TestThemeAutoDetectDarkExplicit(t *testing.T) {
	os.Setenv("COLORFGBG", "15;0")
	defer os.Unsetenv("COLORFGBG")

	theme := NewTheme()
	if !theme.Dark {
		t.Error("expected dark theme when COLORFGBG indicates dark background (0)")
	}
}

func TestSlashCommandParsing(t *testing.T) {
	m := &Model{tier: "mid", gatewayURL: "ws://test", gateway: NewGatewayClient("ws://test")}
	commands := DefaultCommands(m)

	tests := []struct {
		input   string
		wantCmd string
		wantOk  bool
	}{
		{"/help", "help", true},
		{"/exit", "exit", true},
		{"/model high", "model", true},
		{"/tier low", "tier", true},
		{"/unknown", "", false},
		{"hello", "", false},
		{"", "", false},
		{"/status", "status", true},
		{"/new", "new", true},
		{"/abort", "abort", true},
	}

	for _, tt := range tests {
		cmd, _ := ParseSlashCommand(tt.input, commands)
		if tt.wantOk {
			if cmd == nil {
				t.Errorf("ParseSlashCommand(%q): expected command %q, got nil", tt.input, tt.wantCmd)
			} else if cmd.Name != tt.wantCmd {
				t.Errorf("ParseSlashCommand(%q): expected %q, got %q", tt.input, tt.wantCmd, cmd.Name)
			}
		} else {
			if cmd != nil {
				t.Errorf("ParseSlashCommand(%q): expected nil, got %q", tt.input, cmd.Name)
			}
		}
	}
}

func TestSlashCommandArgs(t *testing.T) {
	m := &Model{tier: "mid", gatewayURL: "ws://test", gateway: NewGatewayClient("ws://test")}
	commands := DefaultCommands(m)

	cmd, args := ParseSlashCommand("/model high", commands)
	if cmd == nil {
		t.Fatal("expected model command")
	}
	if args != "high" {
		t.Errorf("expected args %q, got %q", "high", args)
	}
}

func TestChatEntryRenderingUser(t *testing.T) {
	theme := DarkTheme()
	m := Model{theme: theme, width: 80}

	entry := ChatEntry{Role: "user", Content: "Hello Clara"}
	rendered := m.renderEntry(entry, 76)

	if rendered == "" {
		t.Error("user entry rendered as empty string")
	}
	// The rendered output should contain the user content somewhere.
	if !containsText(rendered, "Hello Clara") {
		t.Error("user entry does not contain message text")
	}
}

func TestChatEntryRenderingAssistant(t *testing.T) {
	theme := DarkTheme()
	m := Model{theme: theme, width: 80}

	entry := ChatEntry{Role: "assistant", Content: "Hi there!"}
	rendered := m.renderEntry(entry, 76)

	if rendered == "" {
		t.Error("assistant entry rendered as empty string")
	}
	if !containsText(rendered, "Hi there!") {
		t.Error("assistant entry does not contain message text")
	}
}

func TestChatEntryRenderingSystem(t *testing.T) {
	theme := DarkTheme()
	m := Model{theme: theme, width: 80}

	entry := ChatEntry{Role: "system", Content: "Connected to gateway"}
	rendered := m.renderEntry(entry, 76)

	if !containsText(rendered, "Connected to gateway") {
		t.Error("system entry does not contain message text")
	}
}

func TestChatEntryRenderingTool(t *testing.T) {
	theme := DarkTheme()
	m := Model{theme: theme, width: 80}

	entry := ChatEntry{
		Role: "tool",
		ToolInfo: &ToolInfo{
			Name:   "web_search",
			Status: "success",
			Args:   "query=test",
			Output: "Found 3 results",
		},
	}
	rendered := m.renderEntry(entry, 76)

	if rendered == "" {
		t.Error("tool entry rendered as empty string")
	}
}

func TestNewModelDefaults(t *testing.T) {
	m := NewModel("ws://localhost:18789/ws", "test-user")

	if m.tier != "mid" {
		t.Errorf("expected default tier mid, got %s", m.tier)
	}
	if m.userID != "test-user" {
		t.Errorf("expected userID test-user, got %s", m.userID)
	}
	if m.connected {
		t.Error("expected connected=false initially")
	}
	if m.thinking {
		t.Error("expected thinking=false initially")
	}
	if m.gateway == nil {
		t.Error("expected gateway client to be initialized")
	}
}

func TestGatewayClientNodeID(t *testing.T) {
	c := NewGatewayClient("ws://test")
	if c.NodeID() == "" {
		t.Error("expected non-empty node ID")
	}
	if len(c.NodeID()) < 4 {
		t.Error("expected node ID to have reasonable length")
	}
}

// containsText checks if s contains text, stripping ANSI escape codes.
func containsText(s, text string) bool {
	// Simple check: the text should appear somewhere in the output.
	// ANSI codes may be interspersed, so we do a basic strip.
	stripped := stripANSI(s)
	return len(stripped) > 0 && contains(stripped, text)
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && searchString(s, substr)
}

func searchString(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func stripANSI(s string) string {
	var result []byte
	i := 0
	for i < len(s) {
		if s[i] == '\x1b' && i+1 < len(s) && s[i+1] == '[' {
			// Skip until we find a letter.
			j := i + 2
			for j < len(s) && !((s[j] >= 'A' && s[j] <= 'Z') || (s[j] >= 'a' && s[j] <= 'z')) {
				j++
			}
			if j < len(s) {
				j++ // skip the letter
			}
			i = j
		} else {
			result = append(result, s[i])
			i++
		}
	}
	return string(result)
}
