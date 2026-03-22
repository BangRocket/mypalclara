// Package config provides environment variable loading utilities,
// mirroring the Python mypalclara/config/ module.
package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Init loads environment variables from .env files.
// Searches: current directory, executable's directory, and project root.
// Missing .env files are silently ignored.
func Init() {
	// Try current directory first (standard godotenv behavior)
	_ = godotenv.Load()

	// Also try the executable's directory (for when binary is run from elsewhere)
	if exe, err := os.Executable(); err == nil {
		exeDir := filepath.Dir(exe)
		_ = godotenv.Load(filepath.Join(exeDir, ".env"))
	}

	// Also try common project root locations
	_ = godotenv.Load("../.env")     // if running from go/ subdir
	_ = godotenv.Load("../../.env")  // if running from go/bin/
}

// GetEnv returns the value of the environment variable named by key,
// or fallback if the variable is not set.
func GetEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return fallback
}

// GetEnvBool returns the boolean value of the environment variable named by key.
// Truthy values: "true", "TRUE", "1", "yes" (case-insensitive).
// Falsy values: "false", "FALSE", "0", "no" (case-insensitive).
// Returns fallback if the variable is not set, empty, or unrecognized.
func GetEnvBool(key string, fallback bool) bool {
	v, ok := os.LookupEnv(key)
	if !ok || v == "" {
		return fallback
	}
	switch strings.ToLower(v) {
	case "true", "1", "yes":
		return true
	case "false", "0", "no":
		return false
	default:
		return fallback
	}
}

// GetEnvInt returns the integer value of the environment variable named by key.
// Returns fallback if the variable is not set, empty, or not a valid integer.
func GetEnvInt(key string, fallback int) int {
	v, ok := os.LookupEnv(key)
	if !ok || v == "" {
		return fallback
	}
	i, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return i
}

// GetEnvFloat returns the float64 value of the environment variable named by key.
// Returns fallback if the variable is not set, empty, or not a valid float.
func GetEnvFloat(key string, fallback float64) float64 {
	v, ok := os.LookupEnv(key)
	if !ok || v == "" {
		return fallback
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return fallback
	}
	return f
}

// LLMProvider returns the configured LLM provider name (lowercased).
// Defaults to "openrouter" if LLM_PROVIDER is not set or empty.
func LLMProvider() string {
	v := GetEnv("LLM_PROVIDER", "")
	if v == "" {
		return "openrouter"
	}
	return strings.ToLower(v)
}
