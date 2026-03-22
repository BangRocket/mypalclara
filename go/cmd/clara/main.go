// Command clara starts the Clara gateway server (WebSocket + HTTP API).
//
// Usage:
//
//	./bin/clara                          # gateway only
//	./bin/clara --adapter discord        # gateway + discord adapter
//	./bin/clara -a discord               # same, short flag
//	./bin/clara start --adapter discord  # Python-compatible form
//
// Environment variables:
//   - CLARA_GATEWAY_HOST     (default "127.0.0.1")
//   - CLARA_GATEWAY_PORT     (default 18789)
//   - CLARA_GATEWAY_API_PORT (default 18790)
//   - CLARA_GATEWAY_SECRET   (optional auth secret)
package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/adapters/discord"
	"github.com/BangRocket/mypalclara/go/internal/config"
	"github.com/BangRocket/mypalclara/go/internal/db"
	"github.com/BangRocket/mypalclara/go/internal/gateway"
	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory"
)

func main() {
	// Strip "start" subcommand for Python parity:
	//   ./bin/clara start --adapter discord  →  ./bin/clara --adapter discord
	if len(os.Args) > 1 && os.Args[1] == "start" {
		os.Args = append(os.Args[:1], os.Args[2:]...)
	}

	// Parse flags.
	var adapterFlag string
	flag.StringVar(&adapterFlag, "adapter", "", "comma-separated adapters to start (e.g., discord)")
	flag.StringVar(&adapterFlag, "a", "", "comma-separated adapters to start (short)")
	hostFlag := flag.String("host", "", "override gateway host")
	portFlag := flag.Int("port", 0, "override gateway port")
	flag.Parse()

	// Load .env and configure logging.
	config.Init()
	config.InitLogging()

	logger := config.NewLogger("gateway")
	logger.Info().Msg("Clara gateway starting")

	// Read gateway configuration from environment, with flag overrides.
	host := config.GetEnv("CLARA_GATEWAY_HOST", "127.0.0.1")
	if *hostFlag != "" {
		host = *hostFlag
	}
	wsPort := config.GetEnvInt("CLARA_GATEWAY_PORT", 18789)
	if *portFlag != 0 {
		wsPort = *portFlag
	}
	apiPort := config.GetEnvInt("CLARA_GATEWAY_API_PORT", 18790)
	secret := config.GetEnv("CLARA_GATEWAY_SECRET", "")

	// Initialize database.
	database, err := db.Open()
	if err != nil {
		logger.Fatal().Err(err).Msg("failed to open database")
	}
	defer database.Close()
	logger.Info().Msg("database connected")

	// Create LLM provider.
	provider, err := llm.MakeProviderWithTools(nil)
	if err != nil {
		logger.Fatal().Err(err).Msg("failed to create LLM provider")
	}
	logger.Info().Str("provider", provider.Name()).Msg("LLM provider created")

	// Initialize memory manager.
	mm, err := memory.Initialize(database, provider)
	if err != nil {
		logger.Fatal().Err(err).Msg("failed to initialize memory manager")
	}
	logger.Info().Bool("memory_available", mm.IsAvailable()).Msg("memory manager initialized")

	// Create message processor.
	processor := gateway.NewMessageProcessor(mm, provider)
	processor.SetLogger(config.NewLogger("processor"))

	// Create WebSocket gateway server.
	server := gateway.NewServer(host, wsPort, secret)
	server.SetProcessor(processor)

	// Create HTTP API server.
	api := gateway.NewAPI(host, apiPort, server, processor)
	api.SetLogger(config.NewLogger("api"))

	// Set up signal handling for graceful shutdown.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// Start HTTP API in a goroutine.
	apiErrCh := make(chan error, 1)
	go func() {
		apiErrCh <- api.Start()
	}()

	// Start WebSocket server in a goroutine.
	wsErrCh := make(chan error, 1)
	go func() {
		wsErrCh <- server.Start(ctx)
	}()

	logger.Info().
		Str("host", host).
		Int("ws_port", wsPort).
		Int("api_port", apiPort).
		Msg("gateway servers started")

	// Start adapters.
	adapters := parseAdapters(adapterFlag)
	var discordBot *discord.Bot

	for _, name := range adapters {
		switch name {
		case "discord":
			bot, err := discord.New(discord.ConfigFromEnv()...)
			if err != nil {
				logger.Fatal().Err(err).Msg("failed to create Discord bot")
			}
			discordBot = bot
			go func() {
				if err := bot.Start(ctx); err != nil {
					logger.Error().Err(err).Msg("Discord adapter error")
				}
			}()
			logger.Info().Msg("Discord adapter started")
		default:
			logger.Warn().Str("adapter", name).Msg("unknown adapter, skipping")
		}
	}

	// Wait for signal or server error.
	select {
	case sig := <-sigCh:
		logger.Info().Str("signal", sig.String()).Msg("received shutdown signal")
	case err := <-apiErrCh:
		if err != nil {
			logger.Error().Err(err).Msg("HTTP API error")
		}
	case err := <-wsErrCh:
		if err != nil {
			logger.Error().Err(err).Msg("WebSocket server error")
		}
	}

	// Graceful shutdown.
	logger.Info().Msg("shutting down")
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	// Stop adapters.
	if discordBot != nil {
		if err := discordBot.Stop(); err != nil {
			logger.Error().Err(err).Msg("Discord adapter shutdown error")
		}
	}

	if err := api.Stop(shutdownCtx); err != nil {
		logger.Error().Err(err).Msg("HTTP API shutdown error")
	}

	logger.Info().Msg("Clara gateway stopped")
}

// parseAdapters splits a comma-separated adapter flag into a list of names.
func parseAdapters(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	var result []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}
