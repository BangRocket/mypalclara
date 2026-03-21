// Package discord implements the Discord adapter for MyPalClara's gateway.
//
// It bridges Discord (via discordgo) and the Clara WebSocket gateway,
// translating Discord messages into gateway protocol messages and
// rendering gateway responses back into Discord messages with streaming edits.
package discord

import (
	"strings"

	"github.com/BangRocket/mypalclara/go/internal/config"
)

// ConfigFromEnv creates Discord bot configuration from environment variables.
//
// Reads:
//   - DISCORD_BOT_TOKEN — Discord bot token (required)
//   - DISCORD_ALLOWED_SERVERS — Comma-separated server IDs
//   - DISCORD_ALLOWED_CHANNELS — Comma-separated channel IDs
//   - DISCORD_MAX_MESSAGES — Max conversation chain length (default 25)
//   - DISCORD_STOP_PHRASES — Comma-separated stop phrases
//   - CLARA_GATEWAY_HOST — Gateway host (default 127.0.0.1)
//   - CLARA_GATEWAY_PORT — Gateway port (default 18789)
func ConfigFromEnv() []Option {
	var opts []Option

	if token := config.GetEnv("DISCORD_BOT_TOKEN", ""); token != "" {
		opts = append(opts, WithToken(token))
	}

	host := config.GetEnv("CLARA_GATEWAY_HOST", "")
	if host == "" {
		host = "127.0.0.1"
	}
	port := config.GetEnv("CLARA_GATEWAY_PORT", "")
	if port == "" {
		port = "18789"
	}
	opts = append(opts, WithGatewayURL("ws://"+host+":"+port+"/ws"))

	if servers := config.GetEnv("DISCORD_ALLOWED_SERVERS", ""); servers != "" {
		ids := splitCSV(servers)
		if len(ids) > 0 {
			opts = append(opts, WithAllowedServers(ids))
		}
	}

	if channels := config.GetEnv("DISCORD_ALLOWED_CHANNELS", ""); channels != "" {
		ids := splitCSV(channels)
		if len(ids) > 0 {
			opts = append(opts, WithAllowedChannels(ids))
		}
	}

	if maxMsg := config.GetEnvInt("DISCORD_MAX_MESSAGES", 0); maxMsg > 0 {
		opts = append(opts, WithMaxMessages(maxMsg))
	}

	if phrases := config.GetEnv("DISCORD_STOP_PHRASES", ""); phrases != "" {
		opts = append(opts, WithStopPhrases(splitCSV(phrases)))
	}

	return opts
}

// splitCSV splits a comma-separated string, trimming whitespace from each item.
// Returns nil for empty input.
func splitCSV(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	var result []string
	for _, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}
