package cli

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

// SlashCommand defines a CLI command triggered by typing /<name>.
type SlashCommand struct {
	Name        string
	Description string
	Handler     func(args string) tea.Cmd
}

// DefaultCommands returns the built-in slash commands for the TUI.
func DefaultCommands(m *Model) []SlashCommand {
	return []SlashCommand{
		{
			Name:        "help",
			Description: "Show available commands",
			Handler: func(_ string) tea.Cmd {
				return func() tea.Msg {
					return systemMsg{text: formatHelp(DefaultCommands(m))}
				}
			},
		},
		{
			Name:        "model",
			Description: "Show or set the model tier (high/mid/low)",
			Handler: func(args string) tea.Cmd {
				return func() tea.Msg {
					args = strings.TrimSpace(args)
					if args == "" {
						return systemMsg{text: fmt.Sprintf("Current tier: %s", m.tier)}
					}
					switch strings.ToLower(args) {
					case "high", "mid", "low":
						m.tier = strings.ToLower(args)
						return systemMsg{text: fmt.Sprintf("Tier set to: %s", m.tier)}
					default:
						return systemMsg{text: "Valid tiers: high, mid, low"}
					}
				}
			},
		},
		{
			Name:        "tier",
			Description: "Alias for /model",
			Handler: func(args string) tea.Cmd {
				// Delegate to /model handler.
				for _, cmd := range DefaultCommands(m) {
					if cmd.Name == "model" {
						return cmd.Handler(args)
					}
				}
				return nil
			},
		},
		{
			Name:        "session",
			Description: "Show current session info",
			Handler: func(_ string) tea.Cmd {
				return func() tea.Msg {
					status := "disconnected"
					if m.connected {
						status = "connected"
					}
					return systemMsg{text: fmt.Sprintf(
						"Session: %s\nGateway: %s\nStatus: %s\nMessages: %d",
						m.gateway.NodeID(), m.gatewayURL, status, len(m.chatLog),
					)}
				}
			},
		},
		{
			Name:        "new",
			Description: "Clear chat and start a new conversation",
			Handler: func(_ string) tea.Cmd {
				return func() tea.Msg {
					return clearChatMsg{}
				}
			},
		},
		{
			Name:        "status",
			Description: "Show connection status",
			Handler: func(_ string) tea.Cmd {
				return func() tea.Msg {
					if m.connected {
						return systemMsg{text: fmt.Sprintf("Connected to %s", m.gatewayURL)}
					}
					return systemMsg{text: "Disconnected"}
				}
			},
		},
		{
			Name:        "abort",
			Description: "Cancel the current request",
			Handler: func(_ string) tea.Cmd {
				return func() tea.Msg {
					return cancelRequestMsg{}
				}
			},
		},
		{
			Name:        "exit",
			Description: "Exit the application",
			Handler: func(_ string) tea.Cmd {
				return tea.Quit
			},
		},
	}
}

// ParseSlashCommand checks if input starts with "/" and returns the matching
// command and its arguments. Returns nil if no match.
func ParseSlashCommand(input string, commands []SlashCommand) (*SlashCommand, string) {
	input = strings.TrimSpace(input)
	if !strings.HasPrefix(input, "/") {
		return nil, ""
	}

	parts := strings.SplitN(input[1:], " ", 2)
	name := strings.ToLower(parts[0])
	args := ""
	if len(parts) > 1 {
		args = parts[1]
	}

	for i := range commands {
		if commands[i].Name == name {
			return &commands[i], args
		}
	}
	return nil, ""
}

// formatHelp builds a help text listing all available commands.
func formatHelp(commands []SlashCommand) string {
	var b strings.Builder
	b.WriteString("Available commands:\n")
	for _, cmd := range commands {
		fmt.Fprintf(&b, "  /%-10s %s\n", cmd.Name, cmd.Description)
	}
	b.WriteString("\nKeybindings:\n")
	b.WriteString("  Enter       Send message\n")
	b.WriteString("  Alt+Enter   New line\n")
	b.WriteString("  Esc         Cancel active request\n")
	b.WriteString("  Ctrl+C      Clear input / exit\n")
	b.WriteString("  Up/Down     Input history\n")
	b.WriteString("  PgUp/PgDn   Scroll chat log\n")
	return b.String()
}

// Internal message types for command handlers.
type systemMsg struct{ text string }
type clearChatMsg struct{}
type cancelRequestMsg struct{}
