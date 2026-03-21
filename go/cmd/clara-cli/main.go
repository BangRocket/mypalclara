package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/BangRocket/mypalclara/go/internal/cli"
	"github.com/BangRocket/mypalclara/go/internal/config"
)

func main() {
	config.Init()

	gatewayURL := config.GetEnv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789/ws")
	userID := config.GetEnv("USER_ID", "demo-user")

	model := cli.NewModel(gatewayURL, userID)
	p := tea.NewProgram(model, tea.WithAltScreen())

	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
