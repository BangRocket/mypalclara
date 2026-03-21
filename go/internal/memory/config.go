package memory

import (
	"os"

	"github.com/BangRocket/mypalclara/go/internal/config"
)

// Constants matching the Python memory system.
const (
	MaxSearchQueryChars  = 6000
	MaxKeyMemories       = 15
	MaxMemoriesPerType   = 35
	MaxGraphRelations    = 20
	ContextMessageCount  = 30
	ChannelContextCount  = 50
	SummaryInterval      = 10
	MemoryContextSlice   = 4
	ThreadSummaryMaxMsgs = 30
	DefaultTimezone      = "America/New_York"
)

// RookConfig holds Rook memory system configuration.
type RookConfig struct {
	// Vector store
	VectorStoreProvider string // "qdrant" or "pgvector"
	QdrantURL           string
	QdrantAPIKey        string
	CollectionName      string // default: "clara_memories"

	// Embeddings
	EmbeddingModel string // default: "text-embedding-3-small"
	EmbeddingDims  int    // default: 1536
	OpenAIAPIKey   string

	// LLM for extraction
	RookProvider string // openrouter, nanogpt, openai, anthropic
	RookModel    string // default: "openai/gpt-4o-mini"
	RookAPIKey   string
	RookBaseURL  string

	// Graph (optional)
	EnableGraphMemory  bool
	GraphStoreProvider string // "falkordb"
	FalkorDBHost       string
	FalkorDBPort       int
	FalkorDBPassword   string
	FalkorDBGraphName  string

	// PostgreSQL (optional, for pgvector)
	RookDatabaseURL string

	// Redis (optional, for caching)
	RedisURL string
}

// getEnvWithFallback returns the value of primary env var, falling back to
// secondary, then to the default value.
func getEnvWithFallback(primary, secondary, defaultVal string) string {
	if v, ok := os.LookupEnv(primary); ok && v != "" {
		return v
	}
	if secondary != "" {
		if v, ok := os.LookupEnv(secondary); ok && v != "" {
			return v
		}
	}
	return defaultVal
}

// providerDefaultAPIKey returns the default API key env var for a given
// Rook provider, matching the Python behavior.
func providerDefaultAPIKey(provider string) string {
	switch provider {
	case "openrouter":
		return config.GetEnv("OPENROUTER_API_KEY", "")
	case "nanogpt":
		return config.GetEnv("NANOGPT_API_KEY", "")
	case "openai":
		return config.GetEnv("CUSTOM_OPENAI_API_KEY", "")
	case "anthropic":
		return config.GetEnv("ANTHROPIC_API_KEY", "")
	default:
		return ""
	}
}

// RookConfigFromEnv creates a RookConfig from environment variables.
// Uses ROOK_* prefix with MEM0_* fallback for backward compatibility.
func RookConfigFromEnv() *RookConfig {
	provider := getEnvWithFallback("ROOK_PROVIDER", "MEM0_PROVIDER", "openrouter")
	model := getEnvWithFallback("ROOK_MODEL", "MEM0_MODEL", "openai/gpt-4o-mini")

	// API key: ROOK_API_KEY → MEM0_API_KEY → provider default
	apiKey := getEnvWithFallback("ROOK_API_KEY", "MEM0_API_KEY", "")
	if apiKey == "" {
		apiKey = providerDefaultAPIKey(provider)
	}

	baseURL := getEnvWithFallback("ROOK_BASE_URL", "MEM0_BASE_URL", "")

	// Determine vector store provider
	vectorProvider := "qdrant"
	rookDBURL := config.GetEnv("ROOK_DATABASE_URL", "")
	if rookDBURL != "" {
		vectorProvider = "pgvector"
	}

	return &RookConfig{
		VectorStoreProvider: vectorProvider,
		QdrantURL:           config.GetEnv("QDRANT_URL", "http://localhost:6333"),
		QdrantAPIKey:        config.GetEnv("QDRANT_API_KEY", ""),
		CollectionName:      config.GetEnv("ROOK_COLLECTION_NAME", "clara_memories"),

		EmbeddingModel: config.GetEnv("ROOK_EMBEDDING_MODEL", "text-embedding-3-small"),
		EmbeddingDims:  config.GetEnvInt("ROOK_EMBEDDING_DIMS", 1536),
		OpenAIAPIKey:   config.GetEnv("OPENAI_API_KEY", ""),

		RookProvider: provider,
		RookModel:    model,
		RookAPIKey:   apiKey,
		RookBaseURL:  baseURL,

		EnableGraphMemory:  config.GetEnvBool("ENABLE_GRAPH_MEMORY", false),
		GraphStoreProvider: config.GetEnv("GRAPH_STORE_PROVIDER", "falkordb"),
		FalkorDBHost:       config.GetEnv("FALKORDB_HOST", "localhost"),
		FalkorDBPort:       config.GetEnvInt("FALKORDB_PORT", 6379),
		FalkorDBPassword:   config.GetEnv("FALKORDB_PASSWORD", ""),
		FalkorDBGraphName:  config.GetEnv("FALKORDB_GRAPH_NAME", "clara"),

		RookDatabaseURL: rookDBURL,
		RedisURL:        config.GetEnv("REDIS_URL", ""),
	}
}
