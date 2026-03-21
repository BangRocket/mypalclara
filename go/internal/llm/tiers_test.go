package llm

import (
	"os"
	"testing"
)

// setEnvs sets multiple env vars and returns a cleanup function.
func setEnvs(t *testing.T, vars map[string]string) {
	t.Helper()
	for k, v := range vars {
		t.Setenv(k, v)
	}
}

func TestGetModelForTier_Defaults(t *testing.T) {
	tests := []struct {
		provider string
		tier     ModelTier
		want     string
	}{
		{"openrouter", TierHigh, "anthropic/claude-opus-4"},
		{"openrouter", TierMid, "anthropic/claude-sonnet-4"},
		{"openrouter", TierLow, "anthropic/claude-haiku"},
		{"nanogpt", TierHigh, "anthropic/claude-opus-4"},
		{"nanogpt", TierMid, "moonshotai/Kimi-K2-Instruct-0905"},
		{"nanogpt", TierLow, "openai/gpt-4o-mini"},
		{"openai", TierHigh, "claude-opus-4"},
		{"openai", TierMid, "gpt-4o"},
		{"openai", TierLow, "gpt-4o-mini"},
		{"anthropic", TierHigh, "claude-opus-4-5"},
		{"anthropic", TierMid, "claude-sonnet-4-5"},
		{"anthropic", TierLow, "claude-haiku-4-5"},
		{"bedrock", TierHigh, "anthropic.claude-3-5-sonnet-20241022-v2:0"},
		{"bedrock", TierMid, "anthropic.claude-3-5-sonnet-20241022-v2:0"},
		{"bedrock", TierLow, "anthropic.claude-3-5-haiku-20241022-v1:0"},
		{"azure", TierHigh, "gpt-4o"},
		{"azure", TierMid, "gpt-4o"},
		{"azure", TierLow, "gpt-4o-mini"},
	}

	for _, tt := range tests {
		t.Run(tt.provider+"_"+string(tt.tier), func(t *testing.T) {
			got, err := GetModelForTier(tt.tier, tt.provider)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.want {
				t.Errorf("GetModelForTier(%s, %s) = %q, want %q", tt.tier, tt.provider, got, tt.want)
			}
		})
	}
}

func TestGetModelForTier_EnvOverride(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL_HIGH", "my-custom-opus")
	got, err := GetModelForTier(TierHigh, "anthropic")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "my-custom-opus" {
		t.Errorf("got %q, want %q", got, "my-custom-opus")
	}
}

func TestGetModelForTier_MidFallsBackToBaseEnv(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL", "my-custom-sonnet")
	got, err := GetModelForTier(TierMid, "anthropic")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "my-custom-sonnet" {
		t.Errorf("got %q, want %q", got, "my-custom-sonnet")
	}
}

func TestGetModelForTier_TierEnvOverridesBaseEnv(t *testing.T) {
	t.Setenv("ANTHROPIC_MODEL", "base-model")
	t.Setenv("ANTHROPIC_MODEL_MID", "tier-specific-model")
	got, err := GetModelForTier(TierMid, "anthropic")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "tier-specific-model" {
		t.Errorf("got %q, want %q", got, "tier-specific-model")
	}
}

func TestGetModelForTier_EmptyProviderReadsEnv(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	got, err := GetModelForTier(TierHigh, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "claude-opus-4-5" {
		t.Errorf("got %q, want %q", got, "claude-opus-4-5")
	}
}

func TestGetModelForTier_UnknownProvider(t *testing.T) {
	_, err := GetModelForTier(TierMid, "nonexistent")
	if err == nil {
		t.Fatal("expected error for unknown provider")
	}
}

func TestGetBaseModel_Default(t *testing.T) {
	got, err := GetBaseModel("anthropic")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "claude-sonnet-4-5" {
		t.Errorf("got %q, want %q", got, "claude-sonnet-4-5")
	}
}

func TestGetBaseModel_WithEnvVar(t *testing.T) {
	t.Setenv("OPENROUTER_MODEL", "custom/model")
	got, err := GetBaseModel("openrouter")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "custom/model" {
		t.Errorf("got %q, want %q", got, "custom/model")
	}
}

func TestGetBaseModel_UnknownProvider(t *testing.T) {
	_, err := GetBaseModel("nonexistent")
	if err == nil {
		t.Fatal("expected error for unknown provider")
	}
}

func TestGetCurrentTier_Set(t *testing.T) {
	t.Setenv("MODEL_TIER", "high")
	tier := GetCurrentTier()
	if tier == nil {
		t.Fatal("expected non-nil tier")
	}
	if *tier != TierHigh {
		t.Errorf("got %q, want %q", *tier, TierHigh)
	}
}

func TestGetCurrentTier_Unset(t *testing.T) {
	os.Unsetenv("MODEL_TIER")
	tier := GetCurrentTier()
	if tier != nil {
		t.Errorf("expected nil, got %q", *tier)
	}
}

func TestGetCurrentTier_Invalid(t *testing.T) {
	t.Setenv("MODEL_TIER", "ultra")
	tier := GetCurrentTier()
	if tier != nil {
		t.Errorf("expected nil for invalid tier, got %q", *tier)
	}
}

func TestGetCurrentTier_CaseInsensitive(t *testing.T) {
	t.Setenv("MODEL_TIER", "LOW")
	tier := GetCurrentTier()
	if tier == nil {
		t.Fatal("expected non-nil tier")
	}
	if *tier != TierLow {
		t.Errorf("got %q, want %q", *tier, TierLow)
	}
}

func TestGetToolModel_NilTier(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	got, err := GetToolModel(nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// No MODEL_TIER set, should return base model
	if got != "claude-sonnet-4-5" {
		t.Errorf("got %q, want %q", got, "claude-sonnet-4-5")
	}
}

func TestGetToolModel_LowBumpsToBase(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	low := TierLow
	got, err := GetToolModel(&low)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Low should be bumped to base model (mid default)
	if got != "claude-sonnet-4-5" {
		t.Errorf("got %q, want base model %q", got, "claude-sonnet-4-5")
	}
}

func TestGetToolModel_HighPassesThrough(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	high := TierHigh
	got, err := GetToolModel(&high)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "claude-opus-4-5" {
		t.Errorf("got %q, want %q", got, "claude-opus-4-5")
	}
}

func TestGetToolModel_UsesModelTierEnv(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	t.Setenv("MODEL_TIER", "high")
	got, err := GetToolModel(nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "claude-opus-4-5" {
		t.Errorf("got %q, want %q", got, "claude-opus-4-5")
	}
}

func TestGetTierInfo(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	t.Setenv("MODEL_TIER", "mid")

	info := GetTierInfo()
	if info["provider"] != "anthropic" {
		t.Errorf("provider = %v, want anthropic", info["provider"])
	}
	if info["using_tiers"] != true {
		t.Error("expected using_tiers to be true")
	}
	models, ok := info["models"].(map[string]string)
	if !ok {
		t.Fatal("models should be map[string]string")
	}
	if models["high"] != "claude-opus-4-5" {
		t.Errorf("high model = %q, want claude-opus-4-5", models["high"])
	}
}
