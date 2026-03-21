package memory

import (
	"os"
	"testing"
)

// clearRookEnv unsets all environment variables that RookConfigFromEnv reads
// so tests start from a clean slate.
func clearRookEnv(t *testing.T) {
	t.Helper()
	for _, key := range []string{
		"ROOK_PROVIDER", "MEM0_PROVIDER",
		"ROOK_MODEL", "MEM0_MODEL",
		"ROOK_API_KEY", "MEM0_API_KEY",
		"ROOK_BASE_URL", "MEM0_BASE_URL",
		"ROOK_DATABASE_URL",
		"ROOK_COLLECTION_NAME",
		"ROOK_EMBEDDING_MODEL",
		"ROOK_EMBEDDING_DIMS",
		"QDRANT_URL", "QDRANT_API_KEY",
		"OPENAI_API_KEY",
		"OPENROUTER_API_KEY", "NANOGPT_API_KEY",
		"CUSTOM_OPENAI_API_KEY", "ANTHROPIC_API_KEY",
		"ENABLE_GRAPH_MEMORY",
		"GRAPH_STORE_PROVIDER",
		"FALKORDB_HOST", "FALKORDB_PORT",
		"FALKORDB_PASSWORD", "FALKORDB_GRAPH_NAME",
		"REDIS_URL",
	} {
		os.Unsetenv(key)
	}
}

func TestConfigFromEnvDefaults(t *testing.T) {
	clearRookEnv(t)

	cfg := RookConfigFromEnv()

	if cfg.RookProvider != "openrouter" {
		t.Errorf("RookProvider = %q, want %q", cfg.RookProvider, "openrouter")
	}
	if cfg.RookModel != "openai/gpt-4o-mini" {
		t.Errorf("RookModel = %q, want %q", cfg.RookModel, "openai/gpt-4o-mini")
	}
	if cfg.VectorStoreProvider != "qdrant" {
		t.Errorf("VectorStoreProvider = %q, want %q", cfg.VectorStoreProvider, "qdrant")
	}
	if cfg.QdrantURL != "http://localhost:6333" {
		t.Errorf("QdrantURL = %q, want %q", cfg.QdrantURL, "http://localhost:6333")
	}
	if cfg.CollectionName != "clara_memories" {
		t.Errorf("CollectionName = %q, want %q", cfg.CollectionName, "clara_memories")
	}
	if cfg.EmbeddingModel != "text-embedding-3-small" {
		t.Errorf("EmbeddingModel = %q, want %q", cfg.EmbeddingModel, "text-embedding-3-small")
	}
	if cfg.EmbeddingDims != 1536 {
		t.Errorf("EmbeddingDims = %d, want %d", cfg.EmbeddingDims, 1536)
	}
	if cfg.EnableGraphMemory {
		t.Error("EnableGraphMemory should default to false")
	}
	if cfg.GraphStoreProvider != "falkordb" {
		t.Errorf("GraphStoreProvider = %q, want %q", cfg.GraphStoreProvider, "falkordb")
	}
	if cfg.FalkorDBHost != "localhost" {
		t.Errorf("FalkorDBHost = %q, want %q", cfg.FalkorDBHost, "localhost")
	}
	if cfg.FalkorDBPort != 6379 {
		t.Errorf("FalkorDBPort = %d, want %d", cfg.FalkorDBPort, 6379)
	}
	if cfg.FalkorDBGraphName != "clara" {
		t.Errorf("FalkorDBGraphName = %q, want %q", cfg.FalkorDBGraphName, "clara")
	}
}

func TestConfigFromEnvRookPrefix(t *testing.T) {
	clearRookEnv(t)

	t.Setenv("ROOK_PROVIDER", "anthropic")
	t.Setenv("ROOK_MODEL", "claude-haiku-4-5")
	t.Setenv("ROOK_API_KEY", "rook-key-123")
	t.Setenv("ROOK_BASE_URL", "https://rook.example.com")

	cfg := RookConfigFromEnv()

	if cfg.RookProvider != "anthropic" {
		t.Errorf("RookProvider = %q, want %q", cfg.RookProvider, "anthropic")
	}
	if cfg.RookModel != "claude-haiku-4-5" {
		t.Errorf("RookModel = %q, want %q", cfg.RookModel, "claude-haiku-4-5")
	}
	if cfg.RookAPIKey != "rook-key-123" {
		t.Errorf("RookAPIKey = %q, want %q", cfg.RookAPIKey, "rook-key-123")
	}
	if cfg.RookBaseURL != "https://rook.example.com" {
		t.Errorf("RookBaseURL = %q, want %q", cfg.RookBaseURL, "https://rook.example.com")
	}
}

func TestConfigFromEnvMem0Fallback(t *testing.T) {
	clearRookEnv(t)

	t.Setenv("MEM0_PROVIDER", "nanogpt")
	t.Setenv("MEM0_MODEL", "some-model")
	t.Setenv("MEM0_API_KEY", "mem0-key-456")
	t.Setenv("MEM0_BASE_URL", "https://mem0.example.com")

	cfg := RookConfigFromEnv()

	if cfg.RookProvider != "nanogpt" {
		t.Errorf("RookProvider = %q, want %q (MEM0 fallback)", cfg.RookProvider, "nanogpt")
	}
	if cfg.RookModel != "some-model" {
		t.Errorf("RookModel = %q, want %q (MEM0 fallback)", cfg.RookModel, "some-model")
	}
	if cfg.RookAPIKey != "mem0-key-456" {
		t.Errorf("RookAPIKey = %q, want %q (MEM0 fallback)", cfg.RookAPIKey, "mem0-key-456")
	}
	if cfg.RookBaseURL != "https://mem0.example.com" {
		t.Errorf("RookBaseURL = %q, want %q (MEM0 fallback)", cfg.RookBaseURL, "https://mem0.example.com")
	}

	// ROOK_* should take priority over MEM0_*
	t.Setenv("ROOK_PROVIDER", "openai")
	cfg = RookConfigFromEnv()
	if cfg.RookProvider != "openai" {
		t.Errorf("RookProvider = %q, want %q (ROOK should override MEM0)", cfg.RookProvider, "openai")
	}
}

func TestConfigFromEnvGraphMemory(t *testing.T) {
	clearRookEnv(t)

	t.Setenv("ENABLE_GRAPH_MEMORY", "true")
	t.Setenv("GRAPH_STORE_PROVIDER", "falkordb")
	t.Setenv("FALKORDB_HOST", "graph.example.com")
	t.Setenv("FALKORDB_PORT", "6380")
	t.Setenv("FALKORDB_PASSWORD", "secret")
	t.Setenv("FALKORDB_GRAPH_NAME", "test_graph")

	cfg := RookConfigFromEnv()

	if !cfg.EnableGraphMemory {
		t.Error("EnableGraphMemory should be true")
	}
	if cfg.GraphStoreProvider != "falkordb" {
		t.Errorf("GraphStoreProvider = %q, want %q", cfg.GraphStoreProvider, "falkordb")
	}
	if cfg.FalkorDBHost != "graph.example.com" {
		t.Errorf("FalkorDBHost = %q, want %q", cfg.FalkorDBHost, "graph.example.com")
	}
	if cfg.FalkorDBPort != 6380 {
		t.Errorf("FalkorDBPort = %d, want %d", cfg.FalkorDBPort, 6380)
	}
	if cfg.FalkorDBPassword != "secret" {
		t.Errorf("FalkorDBPassword = %q, want %q", cfg.FalkorDBPassword, "secret")
	}
	if cfg.FalkorDBGraphName != "test_graph" {
		t.Errorf("FalkorDBGraphName = %q, want %q", cfg.FalkorDBGraphName, "test_graph")
	}
}

func TestConfigFromEnvPgvector(t *testing.T) {
	clearRookEnv(t)

	t.Setenv("ROOK_DATABASE_URL", "postgresql://user:pass@host:5432/vectors")

	cfg := RookConfigFromEnv()

	if cfg.VectorStoreProvider != "pgvector" {
		t.Errorf("VectorStoreProvider = %q, want %q when ROOK_DATABASE_URL is set", cfg.VectorStoreProvider, "pgvector")
	}
	if cfg.RookDatabaseURL != "postgresql://user:pass@host:5432/vectors" {
		t.Errorf("RookDatabaseURL = %q, want the set value", cfg.RookDatabaseURL)
	}
}

func TestConfigFromEnvProviderAPIKeyFallback(t *testing.T) {
	clearRookEnv(t)

	// No ROOK_API_KEY set, provider is openrouter (default)
	t.Setenv("OPENROUTER_API_KEY", "or-key-789")

	cfg := RookConfigFromEnv()

	if cfg.RookAPIKey != "or-key-789" {
		t.Errorf("RookAPIKey = %q, want %q (fallback to OPENROUTER_API_KEY)", cfg.RookAPIKey, "or-key-789")
	}

	// Switch provider to anthropic, should pick up ANTHROPIC_API_KEY
	t.Setenv("ROOK_PROVIDER", "anthropic")
	t.Setenv("ANTHROPIC_API_KEY", "ant-key-abc")

	cfg = RookConfigFromEnv()

	if cfg.RookAPIKey != "ant-key-abc" {
		t.Errorf("RookAPIKey = %q, want %q (fallback to ANTHROPIC_API_KEY)", cfg.RookAPIKey, "ant-key-abc")
	}
}
