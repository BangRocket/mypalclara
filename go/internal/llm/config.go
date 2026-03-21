package llm

import (
	"fmt"
	"os"
	"strings"
)

// LLMConfig holds unified configuration for all LLM providers.
type LLMConfig struct {
	Provider        string
	Model           string
	APIKey          string
	BaseURL         string
	MaxTokens       int
	Temperature     float64
	Tier            *ModelTier
	ExtraHeaders    map[string]string
	TopP            float64
	TopK            *int
	AWSRegion       string
	AzureDeployment string
	AzureAPIVersion string
}

// LLMConfigFromEnv creates an LLMConfig from environment variables.
//
// If provider is nil, reads LLM_PROVIDER env var (default "openrouter").
// If tier is nil, reads MODEL_TIER env var if set.
// If forTools is true, applies TOOL_* overrides and prevents "low" tier.
func LLMConfigFromEnv(provider *string, tier *ModelTier, forTools bool) (*LLMConfig, error) {
	p := ""
	if provider != nil {
		p = *provider
	}
	if p == "" {
		p = strings.ToLower(getenvDefault("LLM_PROVIDER", "openrouter"))
	}

	// Determine effective tier
	var effectiveTier *ModelTier
	if tier != nil {
		t := *tier
		effectiveTier = &t
	} else {
		effectiveTier = GetCurrentTier()
	}

	// For tools, never use "low" tier
	if forTools && effectiveTier != nil && *effectiveTier == TierLow {
		effectiveTier = nil
	}

	// Get model based on tier
	var model string
	var err error
	if effectiveTier != nil {
		model, err = GetModelForTier(*effectiveTier, p)
	} else {
		model, err = GetBaseModel(p)
	}
	if err != nil {
		return nil, err
	}

	cfg := &LLMConfig{
		Provider:    p,
		Model:       model,
		MaxTokens:   4096,
		Temperature: 0.0,
		Tier:        effectiveTier,
		TopP:        1.0,
	}

	// Provider-specific configuration
	switch p {
	case "openrouter":
		cfg.APIKey = os.Getenv("OPENROUTER_API_KEY")
		cfg.BaseURL = "https://openrouter.ai/api/v1"
		site := getenvDefault("OPENROUTER_SITE", "http://localhost:3000")
		title := getenvDefault("OPENROUTER_TITLE", "MyPalClara")
		cfg.ExtraHeaders = map[string]string{
			"HTTP-Referer": site,
			"X-Title":      title,
		}

	case "nanogpt":
		cfg.APIKey = os.Getenv("NANOGPT_API_KEY")
		cfg.BaseURL = "https://nano-gpt.com/api/v1"

	case "openai":
		cfg.APIKey = os.Getenv("CUSTOM_OPENAI_API_KEY")
		cfg.BaseURL = getenvDefault("CUSTOM_OPENAI_BASE_URL", "https://api.openai.com/v1")
		cfg.ExtraHeaders = getCFAccessHeaders()

	case "anthropic":
		cfg.APIKey = os.Getenv("ANTHROPIC_API_KEY")
		cfg.BaseURL = os.Getenv("ANTHROPIC_BASE_URL")
		cfg.ExtraHeaders = getCFAccessHeaders()
		// Override User-Agent for proxy compatibility (e.g., clewdr)
		if cfg.BaseURL != "" {
			if cfg.ExtraHeaders == nil {
				cfg.ExtraHeaders = make(map[string]string)
			}
			cfg.ExtraHeaders["User-Agent"] = "Clara/1.0"
		}

	case "bedrock":
		// Amazon Bedrock uses AWS credentials (env vars, IAM role, or profile)
		// No API key needed
		cfg.AWSRegion = getenvDefault("AWS_REGION", "us-east-1")

	case "azure":
		cfg.APIKey = os.Getenv("AZURE_OPENAI_API_KEY")
		cfg.BaseURL = os.Getenv("AZURE_OPENAI_ENDPOINT")
		cfg.AzureDeployment = os.Getenv("AZURE_DEPLOYMENT_NAME")
		cfg.AzureAPIVersion = getenvDefault("AZURE_API_VERSION", "2024-02-15-preview")

	default:
		return nil, fmt.Errorf("unknown provider: %s", p)
	}

	// Apply tool overrides if requested
	if forTools {
		if toolKey := os.Getenv("TOOL_API_KEY"); toolKey != "" {
			cfg.APIKey = toolKey
		}
		if toolURL := os.Getenv("TOOL_BASE_URL"); toolURL != "" {
			cfg.BaseURL = toolURL
		}
	}

	return cfg, nil
}

// WithTier returns a new LLMConfig with a different tier and its corresponding model.
func (c *LLMConfig) WithTier(tier ModelTier) (*LLMConfig, error) {
	model, err := GetModelForTier(tier, c.Provider)
	if err != nil {
		return nil, err
	}

	newCfg := *c // shallow copy
	newCfg.Tier = &tier
	newCfg.Model = model

	// Deep-copy ExtraHeaders
	if c.ExtraHeaders != nil {
		newCfg.ExtraHeaders = make(map[string]string, len(c.ExtraHeaders))
		for k, v := range c.ExtraHeaders {
			newCfg.ExtraHeaders[k] = v
		}
	}

	return &newCfg, nil
}

// getCFAccessHeaders returns Cloudflare Access headers if configured, or nil.
func getCFAccessHeaders() map[string]string {
	clientID := os.Getenv("CF_ACCESS_CLIENT_ID")
	clientSecret := os.Getenv("CF_ACCESS_CLIENT_SECRET")
	if clientID != "" && clientSecret != "" {
		return map[string]string{
			"CF-Access-Client-Id":     clientID,
			"CF-Access-Client-Secret": clientSecret,
		}
	}
	return nil
}
