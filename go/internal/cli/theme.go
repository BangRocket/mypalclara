// Package cli provides an interactive TUI for the Clara gateway using bubbletea.
package cli

import (
	"os"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Theme holds all lipgloss styles used to render the TUI.
type Theme struct {
	Dark      bool
	Header    lipgloss.Style
	UserMsg   lipgloss.Style
	Assistant lipgloss.Style
	System    lipgloss.Style
	ToolBox   lipgloss.Style
	ToolOk    lipgloss.Style
	ToolErr   lipgloss.Style
	Status    lipgloss.Style
	Editor    lipgloss.Style
	Dim       lipgloss.Style
}

// NewTheme auto-detects dark/light mode from COLORFGBG and returns the
// appropriate theme. Falls back to dark theme when detection is ambiguous.
func NewTheme() *Theme {
	if isLightTerminal() {
		return LightTheme()
	}
	return DarkTheme()
}

// DarkTheme returns a theme suited for dark terminal backgrounds.
func DarkTheme() *Theme {
	return &Theme{
		Dark: true,
		Header: lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("219")).
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("63")).
			Padding(0, 1),
		UserMsg: lipgloss.NewStyle().
			Foreground(lipgloss.Color("252")).
			Background(lipgloss.Color("236")).
			Padding(0, 1),
		Assistant: lipgloss.NewStyle().
			Foreground(lipgloss.Color("252")),
		System: lipgloss.NewStyle().
			Foreground(lipgloss.Color("245")).
			Italic(true),
		ToolBox: lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("63")).
			Padding(0, 1),
		ToolOk: lipgloss.NewStyle().
			Foreground(lipgloss.Color("78")),
		ToolErr: lipgloss.NewStyle().
			Foreground(lipgloss.Color("204")),
		Status: lipgloss.NewStyle().
			Foreground(lipgloss.Color("245")).
			Background(lipgloss.Color("236")).
			Padding(0, 1),
		Editor: lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240")).
			Padding(0, 1),
		Dim: lipgloss.NewStyle().
			Foreground(lipgloss.Color("242")),
	}
}

// LightTheme returns a theme suited for light terminal backgrounds.
func LightTheme() *Theme {
	return &Theme{
		Dark: false,
		Header: lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("55")).
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("63")).
			Padding(0, 1),
		UserMsg: lipgloss.NewStyle().
			Foreground(lipgloss.Color("232")).
			Background(lipgloss.Color("254")).
			Padding(0, 1),
		Assistant: lipgloss.NewStyle().
			Foreground(lipgloss.Color("232")),
		System: lipgloss.NewStyle().
			Foreground(lipgloss.Color("240")).
			Italic(true),
		ToolBox: lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("63")).
			Padding(0, 1),
		ToolOk: lipgloss.NewStyle().
			Foreground(lipgloss.Color("28")),
		ToolErr: lipgloss.NewStyle().
			Foreground(lipgloss.Color("160")),
		Status: lipgloss.NewStyle().
			Foreground(lipgloss.Color("240")).
			Background(lipgloss.Color("254")).
			Padding(0, 1),
		Editor: lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("248")).
			Padding(0, 1),
		Dim: lipgloss.NewStyle().
			Foreground(lipgloss.Color("245")),
	}
}

// isLightTerminal attempts to detect a light terminal background using the
// COLORFGBG environment variable (format: "fg;bg"). A bg value >= 8 is
// typically light.
func isLightTerminal() bool {
	v := os.Getenv("COLORFGBG")
	if v == "" {
		return false
	}
	parts := strings.Split(v, ";")
	if len(parts) < 2 {
		return false
	}
	bg := parts[len(parts)-1]
	// Values 0-6 and 8 are typically dark; 7 and 9-15 are light.
	switch bg {
	case "7", "9", "10", "11", "12", "13", "14", "15":
		return true
	default:
		return false
	}
}
