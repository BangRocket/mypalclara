package config

import (
	"io"
	"os"
	"strings"

	"github.com/rs/zerolog"
)

// getLogLevel reads the LOG_LEVEL environment variable and returns the
// corresponding zerolog.Level. Recognized values (case-insensitive):
// DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL. Defaults to InfoLevel.
func getLogLevel() zerolog.Level {
	raw := strings.ToUpper(os.Getenv("LOG_LEVEL"))
	switch raw {
	case "DEBUG":
		return zerolog.DebugLevel
	case "INFO":
		return zerolog.InfoLevel
	case "WARN", "WARNING":
		return zerolog.WarnLevel
	case "ERROR":
		return zerolog.ErrorLevel
	case "CRITICAL":
		return zerolog.FatalLevel
	default:
		return zerolog.InfoLevel
	}
}

// InitLogging sets zerolog global defaults: RFC3339 time format and
// the log level from the LOG_LEVEL environment variable.
func InitLogging() {
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	zerolog.SetGlobalLevel(getLogLevel())
}

// NewLogger creates a named logger that writes to stderr with
// human-readable console formatting. All output goes to stderr
// for MCP compatibility (stdout is reserved for JSON-RPC).
func NewLogger(name string) zerolog.Logger {
	return NewLoggerTo(name, os.Stderr)
}

// NewLoggerTo creates a named logger that writes to the specified writer
// with human-readable console formatting.
func NewLoggerTo(name string, w io.Writer) zerolog.Logger {
	cw := zerolog.ConsoleWriter{Out: w, TimeFormat: "15:04:05"}
	return zerolog.New(cw).With().Timestamp().Str("component", name).Logger()
}
