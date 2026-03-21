package config

import (
	"bytes"
	"testing"

	"github.com/rs/zerolog"
)

func TestNewLogger(t *testing.T) {
	var buf bytes.Buffer
	logger := NewLoggerTo("test-component", &buf)

	logger.Info().Msg("hello world")

	out := buf.String()
	if out == "" {
		t.Fatal("expected output, got empty string")
	}
	if !bytes.Contains([]byte(out), []byte("hello world")) {
		t.Errorf("expected output to contain 'hello world', got: %s", out)
	}
	if !bytes.Contains([]byte(out), []byte("test-component")) {
		t.Errorf("expected output to contain component name 'test-component', got: %s", out)
	}
}

func TestLoggerLevel(t *testing.T) {
	var buf bytes.Buffer
	logger := NewLoggerTo("level-test", &buf).Level(zerolog.WarnLevel)

	// INFO should be suppressed at WARN level
	logger.Info().Msg("should not appear")
	if buf.Len() != 0 {
		t.Errorf("expected INFO to be suppressed at WARN level, got: %s", buf.String())
	}

	// WARN should pass through
	logger.Warn().Msg("warning message")
	if buf.Len() == 0 {
		t.Error("expected WARN message to appear, got empty output")
	}
	if !bytes.Contains(buf.Bytes(), []byte("warning message")) {
		t.Errorf("expected output to contain 'warning message', got: %s", buf.String())
	}
}

func TestGetLogLevel(t *testing.T) {
	tests := []struct {
		env  string
		want zerolog.Level
	}{
		{"DEBUG", zerolog.DebugLevel},
		{"INFO", zerolog.InfoLevel},
		{"WARN", zerolog.WarnLevel},
		{"WARNING", zerolog.WarnLevel},
		{"ERROR", zerolog.ErrorLevel},
		{"", zerolog.InfoLevel},
		{"garbage", zerolog.InfoLevel},
		{"debug", zerolog.DebugLevel},   // case-insensitive
		{"Warning", zerolog.WarnLevel},  // mixed case
	}

	for _, tt := range tests {
		t.Run("LOG_LEVEL="+tt.env, func(t *testing.T) {
			if tt.env != "" {
				t.Setenv("LOG_LEVEL", tt.env)
			} else {
				t.Setenv("LOG_LEVEL", "")
			}

			got := getLogLevel()
			if got != tt.want {
				t.Errorf("getLogLevel() with LOG_LEVEL=%q = %v, want %v", tt.env, got, tt.want)
			}
		})
	}
}
