package llm

import "fmt"

// GetProvider creates a Provider based on LLMConfig.
func GetProvider(config *LLMConfig) (Provider, error) {
	switch config.Provider {
	case "openrouter", "nanogpt", "openai":
		return NewOpenAIProvider(config)
	case "anthropic":
		return NewAnthropicProvider(config)
	// bedrock and azure not yet implemented
	default:
		return nil, fmt.Errorf("unsupported provider: %s", config.Provider)
	}
}

// MakeProvider creates a Provider from environment configuration.
// tier can be nil for default.
func MakeProvider(tier *ModelTier) (Provider, error) {
	config, err := LLMConfigFromEnv(nil, tier, false)
	if err != nil {
		return nil, err
	}
	return GetProvider(config)
}

// MakeProviderWithTools creates a Provider configured for tool calling.
// Uses TOOL_* overrides and never uses "low" tier.
func MakeProviderWithTools(tier *ModelTier) (Provider, error) {
	config, err := LLMConfigFromEnv(nil, tier, true)
	if err != nil {
		return nil, err
	}
	return GetProvider(config)
}
