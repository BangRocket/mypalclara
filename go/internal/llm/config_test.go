package llm

import (
	"testing"
)

func TestLLMConfigFromEnv_OpenRouter(t *testing.T) {
	t.Setenv("OPENROUTER_API_KEY", "or-key-123")
	t.Setenv("OPENROUTER_SITE", "https://mysite.com")
	t.Setenv("OPENROUTER_TITLE", "TestApp")

	provider := "openrouter"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Provider != "openrouter" {
		t.Errorf("Provider = %q, want openrouter", cfg.Provider)
	}
	if cfg.APIKey != "or-key-123" {
		t.Errorf("APIKey = %q, want or-key-123", cfg.APIKey)
	}
	if cfg.BaseURL != "https://openrouter.ai/api/v1" {
		t.Errorf("BaseURL = %q, want https://openrouter.ai/api/v1", cfg.BaseURL)
	}
	if cfg.Model != "anthropic/claude-sonnet-4" {
		t.Errorf("Model = %q, want anthropic/claude-sonnet-4", cfg.Model)
	}
	if cfg.ExtraHeaders["HTTP-Referer"] != "https://mysite.com" {
		t.Errorf("HTTP-Referer = %q, want https://mysite.com", cfg.ExtraHeaders["HTTP-Referer"])
	}
	if cfg.ExtraHeaders["X-Title"] != "TestApp" {
		t.Errorf("X-Title = %q, want TestApp", cfg.ExtraHeaders["X-Title"])
	}
}

func TestLLMConfigFromEnv_NanoGPT(t *testing.T) {
	t.Setenv("NANOGPT_API_KEY", "ng-key-456")

	provider := "nanogpt"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.APIKey != "ng-key-456" {
		t.Errorf("APIKey = %q, want ng-key-456", cfg.APIKey)
	}
	if cfg.BaseURL != "https://nano-gpt.com/api/v1" {
		t.Errorf("BaseURL = %q, want https://nano-gpt.com/api/v1", cfg.BaseURL)
	}
	if cfg.ExtraHeaders != nil {
		t.Errorf("ExtraHeaders should be nil for nanogpt, got %v", cfg.ExtraHeaders)
	}
}

func TestLLMConfigFromEnv_OpenAI(t *testing.T) {
	t.Setenv("CUSTOM_OPENAI_API_KEY", "oai-key-789")
	t.Setenv("CUSTOM_OPENAI_BASE_URL", "https://custom.api.com/v1")

	provider := "openai"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.APIKey != "oai-key-789" {
		t.Errorf("APIKey = %q, want oai-key-789", cfg.APIKey)
	}
	if cfg.BaseURL != "https://custom.api.com/v1" {
		t.Errorf("BaseURL = %q, want https://custom.api.com/v1", cfg.BaseURL)
	}
}

func TestLLMConfigFromEnv_OpenAI_DefaultBaseURL(t *testing.T) {
	t.Setenv("CUSTOM_OPENAI_API_KEY", "key")

	provider := "openai"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.BaseURL != "https://api.openai.com/v1" {
		t.Errorf("BaseURL = %q, want https://api.openai.com/v1", cfg.BaseURL)
	}
}

func TestLLMConfigFromEnv_Anthropic(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "ant-key")

	provider := "anthropic"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.APIKey != "ant-key" {
		t.Errorf("APIKey = %q, want ant-key", cfg.APIKey)
	}
	if cfg.BaseURL != "" {
		t.Errorf("BaseURL should be empty when ANTHROPIC_BASE_URL not set, got %q", cfg.BaseURL)
	}
	if cfg.Model != "claude-sonnet-4-5" {
		t.Errorf("Model = %q, want claude-sonnet-4-5", cfg.Model)
	}
}

func TestLLMConfigFromEnv_Anthropic_WithBaseURL(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "ant-key")
	t.Setenv("ANTHROPIC_BASE_URL", "https://proxy.example.com")

	provider := "anthropic"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.BaseURL != "https://proxy.example.com" {
		t.Errorf("BaseURL = %q, want https://proxy.example.com", cfg.BaseURL)
	}
	if cfg.ExtraHeaders["User-Agent"] != "Clara/1.0" {
		t.Errorf("User-Agent header = %q, want Clara/1.0", cfg.ExtraHeaders["User-Agent"])
	}
}

func TestLLMConfigFromEnv_Bedrock(t *testing.T) {
	t.Setenv("AWS_REGION", "eu-west-1")

	provider := "bedrock"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.APIKey != "" {
		t.Errorf("APIKey should be empty for bedrock, got %q", cfg.APIKey)
	}
	if cfg.AWSRegion != "eu-west-1" {
		t.Errorf("AWSRegion = %q, want eu-west-1", cfg.AWSRegion)
	}
}

func TestLLMConfigFromEnv_Azure(t *testing.T) {
	t.Setenv("AZURE_OPENAI_API_KEY", "azure-key")
	t.Setenv("AZURE_OPENAI_ENDPOINT", "https://myresource.openai.azure.com")
	t.Setenv("AZURE_DEPLOYMENT_NAME", "gpt4o-deploy")
	t.Setenv("AZURE_API_VERSION", "2024-06-01")

	provider := "azure"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.APIKey != "azure-key" {
		t.Errorf("APIKey = %q, want azure-key", cfg.APIKey)
	}
	if cfg.BaseURL != "https://myresource.openai.azure.com" {
		t.Errorf("BaseURL = %q, want endpoint URL", cfg.BaseURL)
	}
	if cfg.AzureDeployment != "gpt4o-deploy" {
		t.Errorf("AzureDeployment = %q, want gpt4o-deploy", cfg.AzureDeployment)
	}
	if cfg.AzureAPIVersion != "2024-06-01" {
		t.Errorf("AzureAPIVersion = %q, want 2024-06-01", cfg.AzureAPIVersion)
	}
}

func TestLLMConfigFromEnv_UnknownProvider(t *testing.T) {
	provider := "nonexistent"
	_, err := LLMConfigFromEnv(&provider, nil, false)
	if err == nil {
		t.Fatal("expected error for unknown provider")
	}
}

func TestLLMConfigFromEnv_NilProviderReadsEnv(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "anthropic")
	t.Setenv("ANTHROPIC_API_KEY", "key")

	cfg, err := LLMConfigFromEnv(nil, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Provider != "anthropic" {
		t.Errorf("Provider = %q, want anthropic", cfg.Provider)
	}
}

func TestLLMConfigFromEnv_WithTier(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "key")

	provider := "anthropic"
	tier := TierHigh
	cfg, err := LLMConfigFromEnv(&provider, &tier, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Model != "claude-opus-4-5" {
		t.Errorf("Model = %q, want claude-opus-4-5", cfg.Model)
	}
	if cfg.Tier == nil || *cfg.Tier != TierHigh {
		t.Errorf("Tier = %v, want high", cfg.Tier)
	}
}

func TestLLMConfigFromEnv_ForTools_LowBumped(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "key")

	provider := "anthropic"
	tier := TierLow
	cfg, err := LLMConfigFromEnv(&provider, &tier, true)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Low tier should be bumped to base model for tools
	if cfg.Model != "claude-sonnet-4-5" {
		t.Errorf("Model = %q, want claude-sonnet-4-5 (low bumped to base)", cfg.Model)
	}
	if cfg.Tier != nil {
		t.Errorf("Tier should be nil after low bump, got %v", *cfg.Tier)
	}
}

func TestLLMConfigFromEnv_ForTools_ToolOverrides(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "original-key")
	t.Setenv("TOOL_API_KEY", "tool-key")
	t.Setenv("TOOL_BASE_URL", "https://tool-proxy.com/v1")

	provider := "anthropic"
	cfg, err := LLMConfigFromEnv(&provider, nil, true)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.APIKey != "tool-key" {
		t.Errorf("APIKey = %q, want tool-key", cfg.APIKey)
	}
	if cfg.BaseURL != "https://tool-proxy.com/v1" {
		t.Errorf("BaseURL = %q, want https://tool-proxy.com/v1", cfg.BaseURL)
	}
}

func TestLLMConfigFromEnv_CFAccessHeaders(t *testing.T) {
	t.Setenv("CUSTOM_OPENAI_API_KEY", "key")
	t.Setenv("CF_ACCESS_CLIENT_ID", "cf-id")
	t.Setenv("CF_ACCESS_CLIENT_SECRET", "cf-secret")

	provider := "openai"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.ExtraHeaders == nil {
		t.Fatal("ExtraHeaders should not be nil with CF Access configured")
	}
	if cfg.ExtraHeaders["CF-Access-Client-Id"] != "cf-id" {
		t.Errorf("CF-Access-Client-Id = %q, want cf-id", cfg.ExtraHeaders["CF-Access-Client-Id"])
	}
	if cfg.ExtraHeaders["CF-Access-Client-Secret"] != "cf-secret" {
		t.Errorf("CF-Access-Client-Secret = %q, want cf-secret", cfg.ExtraHeaders["CF-Access-Client-Secret"])
	}
}

func TestWithTier(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "key")

	provider := "anthropic"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	highCfg, err := cfg.WithTier(TierHigh)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Original should be unchanged
	if cfg.Model != "claude-sonnet-4-5" {
		t.Errorf("original Model changed to %q", cfg.Model)
	}

	// New config should have high tier model
	if highCfg.Model != "claude-opus-4-5" {
		t.Errorf("WithTier Model = %q, want claude-opus-4-5", highCfg.Model)
	}
	if highCfg.Tier == nil || *highCfg.Tier != TierHigh {
		t.Errorf("WithTier Tier = %v, want high", highCfg.Tier)
	}

	// Should preserve other fields
	if highCfg.APIKey != cfg.APIKey {
		t.Error("WithTier should preserve APIKey")
	}
	if highCfg.Provider != cfg.Provider {
		t.Error("WithTier should preserve Provider")
	}
}

func TestWithTier_DeepCopiesHeaders(t *testing.T) {
	t.Setenv("OPENROUTER_API_KEY", "key")

	provider := "openrouter"
	cfg, err := LLMConfigFromEnv(&provider, nil, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	highCfg, err := cfg.WithTier(TierHigh)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Mutating new config's headers shouldn't affect original
	highCfg.ExtraHeaders["X-New"] = "value"
	if _, ok := cfg.ExtraHeaders["X-New"]; ok {
		t.Error("WithTier should deep-copy ExtraHeaders")
	}
}
