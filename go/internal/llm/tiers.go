package llm

import (
	"fmt"
	"os"
	"strings"
)

// ModelTier represents a capability/cost tradeoff level for LLM model selection.
type ModelTier string

const (
	TierHigh ModelTier = "high"
	TierMid  ModelTier = "mid"
	TierLow  ModelTier = "low"
)

// DefaultTier is the default model tier when none is specified.
const DefaultTier = TierMid

// DefaultModels maps provider → tier → default model name.
var DefaultModels = map[string]map[ModelTier]string{
	"openrouter": {
		TierHigh: "anthropic/claude-opus-4",
		TierMid:  "anthropic/claude-sonnet-4",
		TierLow:  "anthropic/claude-haiku",
	},
	"nanogpt": {
		TierHigh: "anthropic/claude-opus-4",
		TierMid:  "moonshotai/Kimi-K2-Instruct-0905",
		TierLow:  "openai/gpt-4o-mini",
	},
	"openai": {
		TierHigh: "claude-opus-4",
		TierMid:  "gpt-4o",
		TierLow:  "gpt-4o-mini",
	},
	"anthropic": {
		TierHigh: "claude-opus-4-5",
		TierMid:  "claude-sonnet-4-5",
		TierLow:  "claude-haiku-4-5",
	},
	"bedrock": {
		TierHigh: "anthropic.claude-3-5-sonnet-20241022-v2:0",
		TierMid:  "anthropic.claude-3-5-sonnet-20241022-v2:0",
		TierLow:  "anthropic.claude-3-5-haiku-20241022-v1:0",
	},
	"azure": {
		TierHigh: "gpt-4o",
		TierMid:  "gpt-4o",
		TierLow:  "gpt-4o-mini",
	},
}

// providerEnvPrefixes maps provider name to its env-var prefix for model config.
var providerEnvPrefixes = map[string]string{
	"openrouter": "OPENROUTER",
	"nanogpt":    "NANOGPT",
	"openai":     "CUSTOM_OPENAI",
	"anthropic":  "ANTHROPIC",
	"bedrock":    "BEDROCK",
	"azure":      "AZURE",
}

// GetModelForTier returns the model name for a given tier and provider.
//
// Resolution order:
//  1. Tier-specific env var (e.g. ANTHROPIC_MODEL_HIGH)
//  2. For mid tier: base model env var (e.g. ANTHROPIC_MODEL)
//  3. Default from DefaultModels
//
// If provider is empty, reads LLM_PROVIDER env var (default "openrouter").
func GetModelForTier(tier ModelTier, provider string) (string, error) {
	if provider == "" {
		provider = strings.ToLower(getenvDefault("LLM_PROVIDER", "openrouter"))
	}

	prefix, ok := providerEnvPrefixes[provider]
	if !ok {
		return "", fmt.Errorf("unknown provider: %s", provider)
	}

	defaults, ok := DefaultModels[provider]
	if !ok {
		return "", fmt.Errorf("unknown provider: %s", provider)
	}

	tierUpper := strings.ToUpper(string(tier))

	// 1. Check tier-specific env var
	tierModel := os.Getenv(prefix + "_MODEL_" + tierUpper)
	if tierModel != "" {
		return tierModel, nil
	}

	// 2. For mid tier, fall back to base model env var
	if tier == TierMid {
		baseModel := os.Getenv(prefix + "_MODEL")
		if baseModel != "" {
			return baseModel, nil
		}
	}

	// 3. Default
	if model, ok := defaults[tier]; ok {
		return model, nil
	}
	return defaults[TierMid], nil
}

// GetBaseModel returns the base model for a provider (without tier suffix).
//
// Reads the base env var (e.g. ANTHROPIC_MODEL), falling back to the mid-tier default.
// If provider is empty, reads LLM_PROVIDER env var (default "openrouter").
func GetBaseModel(provider string) (string, error) {
	if provider == "" {
		provider = strings.ToLower(getenvDefault("LLM_PROVIDER", "openrouter"))
	}

	prefix, ok := providerEnvPrefixes[provider]
	if !ok {
		return "", fmt.Errorf("unknown provider: %s", provider)
	}

	defaults, ok := DefaultModels[provider]
	if !ok {
		return "", fmt.Errorf("unknown provider: %s", provider)
	}

	baseModel := os.Getenv(prefix + "_MODEL")
	if baseModel != "" {
		return baseModel, nil
	}
	return defaults[TierMid], nil
}

// GetCurrentTier returns the current default tier from the MODEL_TIER env var.
// Returns nil if MODEL_TIER is not set or is invalid.
func GetCurrentTier() *ModelTier {
	tier := strings.ToLower(os.Getenv("MODEL_TIER"))
	switch tier {
	case "high":
		t := TierHigh
		return &t
	case "mid":
		t := TierMid
		return &t
	case "low":
		t := TierLow
		return &t
	default:
		return nil
	}
}

// GetTierInfo returns information about configured tiers for the current provider.
func GetTierInfo() map[string]any {
	provider := strings.ToLower(getenvDefault("LLM_PROVIDER", "openrouter"))
	currentTier := GetCurrentTier()
	defaultModel, _ := GetBaseModel(provider)

	highModel, _ := GetModelForTier(TierHigh, provider)
	midModel, _ := GetModelForTier(TierMid, provider)
	lowModel, _ := GetModelForTier(TierLow, provider)

	var tierStr *string
	if currentTier != nil {
		s := string(*currentTier)
		tierStr = &s
	}

	return map[string]any{
		"provider":      provider,
		"current_tier":  tierStr,
		"default_model": defaultModel,
		"using_tiers":   currentTier != nil,
		"models": map[string]string{
			"high": highModel,
			"mid":  midModel,
			"low":  lowModel,
		},
	}
}

// GetToolModel returns the model to use for tool calling.
//
// Tool calls never use "low" tier — they use the base model at minimum.
// This ensures tools always have sufficient capability.
func GetToolModel(tier *ModelTier) (string, error) {
	provider := strings.ToLower(getenvDefault("LLM_PROVIDER", "openrouter"))

	// Never use "low" tier for tools
	if tier != nil && *tier == TierLow {
		return GetBaseModel(provider)
	}

	// For other tiers (high, mid), use tier-based selection
	effectiveTier := tier
	if effectiveTier == nil {
		effectiveTier = GetCurrentTier()
	}

	// If no tier specified and MODEL_TIER not set, use base model
	if effectiveTier == nil {
		return GetBaseModel(provider)
	}

	return GetModelForTier(*effectiveTier, provider)
}

// getenvDefault returns the value of the environment variable named by the key,
// or fallback if the variable is not set or empty.
func getenvDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
