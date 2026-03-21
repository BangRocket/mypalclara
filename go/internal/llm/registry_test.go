package llm

import "testing"

func TestGetProviderOpenRouter(t *testing.T) {
	config := &LLMConfig{Provider: "openrouter", APIKey: "test", BaseURL: "https://openrouter.ai/api/v1", Model: "test"}
	p, err := GetProvider(config)
	if err != nil {
		t.Fatal(err)
	}
	if p.Name() != "openrouter" {
		t.Errorf("Name() = %q, want %q", p.Name(), "openrouter")
	}
}

func TestGetProviderAnthropic(t *testing.T) {
	config := &LLMConfig{Provider: "anthropic", APIKey: "test", Model: "claude-sonnet-4-5"}
	p, err := GetProvider(config)
	if err != nil {
		t.Fatal(err)
	}
	if p.Name() != "anthropic" {
		t.Errorf("Name() = %q, want %q", p.Name(), "anthropic")
	}
}

func TestGetProviderUnsupported(t *testing.T) {
	config := &LLMConfig{Provider: "unknown"}
	_, err := GetProvider(config)
	if err == nil {
		t.Error("expected error for unknown provider")
	}
}

func TestMakeProviderFromEnv(t *testing.T) {
	t.Setenv("LLM_PROVIDER", "openrouter")
	t.Setenv("OPENROUTER_API_KEY", "test-key")
	p, err := MakeProvider(nil)
	if err != nil {
		t.Fatal(err)
	}
	if p == nil {
		t.Error("provider should not be nil")
	}
}
