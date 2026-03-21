package config

import (
	"os"
	"testing"
)

func TestGetEnv(t *testing.T) {
	tests := []struct {
		name     string
		key      string
		setVal   *string // nil means don't set
		fallback string
		want     string
	}{
		{"missing key returns fallback", "TEST_MISSING_KEY_XYZ", nil, "default", "default"},
		{"set key returns value", "TEST_SET_KEY", strPtr("hello"), "default", "hello"},
		{"empty value returns empty", "TEST_EMPTY_KEY", strPtr(""), "default", ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.setVal != nil {
				os.Setenv(tt.key, *tt.setVal)
				defer os.Unsetenv(tt.key)
			} else {
				os.Unsetenv(tt.key)
			}
			got := GetEnv(tt.key, tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnv(%q, %q) = %q, want %q", tt.key, tt.fallback, got, tt.want)
			}
		})
	}
}

func TestGetEnvBool(t *testing.T) {
	tests := []struct {
		name     string
		setVal   *string
		fallback bool
		want     bool
	}{
		{"true", strPtr("true"), false, true},
		{"TRUE", strPtr("TRUE"), false, true},
		{"1", strPtr("1"), false, true},
		{"yes", strPtr("yes"), false, true},
		{"Yes", strPtr("Yes"), false, true},
		{"false", strPtr("false"), true, false},
		{"0", strPtr("0"), true, false},
		{"no", strPtr("no"), true, false},
		{"empty returns fallback true", strPtr(""), true, true},
		{"empty returns fallback false", strPtr(""), false, false},
		{"missing returns fallback true", nil, true, true},
		{"missing returns fallback false", nil, false, false},
		{"invalid returns fallback", strPtr("banana"), false, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_BOOL_KEY"
			if tt.setVal != nil {
				os.Setenv(key, *tt.setVal)
				defer os.Unsetenv(key)
			} else {
				os.Unsetenv(key)
			}
			got := GetEnvBool(key, tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnvBool(%q, %v) = %v, want %v", key, tt.fallback, got, tt.want)
			}
		})
	}
}

func TestGetEnvInt(t *testing.T) {
	tests := []struct {
		name     string
		setVal   *string
		fallback int
		want     int
	}{
		{"valid int", strPtr("42"), 0, 42},
		{"negative int", strPtr("-5"), 0, -5},
		{"invalid returns fallback", strPtr("abc"), 10, 10},
		{"missing returns fallback", nil, 99, 99},
		{"empty returns fallback", strPtr(""), 7, 7},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_INT_KEY"
			if tt.setVal != nil {
				os.Setenv(key, *tt.setVal)
				defer os.Unsetenv(key)
			} else {
				os.Unsetenv(key)
			}
			got := GetEnvInt(key, tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnvInt(%q, %d) = %d, want %d", key, tt.fallback, got, tt.want)
			}
		})
	}
}

func TestGetEnvFloat(t *testing.T) {
	tests := []struct {
		name     string
		setVal   *string
		fallback float64
		want     float64
	}{
		{"valid float", strPtr("3.14"), 0, 3.14},
		{"integer as float", strPtr("42"), 0, 42.0},
		{"invalid returns fallback", strPtr("abc"), 1.5, 1.5},
		{"missing returns fallback", nil, 2.5, 2.5},
		{"empty returns fallback", strPtr(""), 9.9, 9.9},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_FLOAT_KEY"
			if tt.setVal != nil {
				os.Setenv(key, *tt.setVal)
				defer os.Unsetenv(key)
			} else {
				os.Unsetenv(key)
			}
			got := GetEnvFloat(key, tt.fallback)
			if got != tt.want {
				t.Errorf("GetEnvFloat(%q, %f) = %f, want %f", key, tt.fallback, got, tt.want)
			}
		})
	}
}

func TestLLMProvider(t *testing.T) {
	tests := []struct {
		name   string
		setVal *string
		want   string
	}{
		{"default", nil, "openrouter"},
		{"set value", strPtr("anthropic"), "anthropic"},
		{"uppercased is lowered", strPtr("Anthropic"), "anthropic"},
		{"empty returns default", strPtr(""), "openrouter"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.setVal != nil {
				os.Setenv("LLM_PROVIDER", *tt.setVal)
				defer os.Unsetenv("LLM_PROVIDER")
			} else {
				os.Unsetenv("LLM_PROVIDER")
			}
			got := LLMProvider()
			if got != tt.want {
				t.Errorf("LLMProvider() = %q, want %q", got, tt.want)
			}
		})
	}
}

func strPtr(s string) *string {
	return &s
}
