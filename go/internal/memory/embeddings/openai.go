package embeddings

import (
	"context"
	"errors"
	"fmt"
	"os"

	openai "github.com/sashabaranov/go-openai"
)

const (
	defaultModel = "text-embedding-3-small"
	defaultDims  = 1536
)

// OpenAIEmbedder generates embeddings using the OpenAI API.
type OpenAIEmbedder struct {
	client *openai.Client
	model  string
	dims   int
}

// Option configures an OpenAIEmbedder.
type Option func(*openAIConfig)

type openAIConfig struct {
	model   string
	dims    int
	apiKey  string
	baseURL string
}

// WithModel sets the embedding model.
func WithModel(model string) Option {
	return func(c *openAIConfig) {
		c.model = model
	}
}

// WithDims sets the embedding dimensions.
func WithDims(dims int) Option {
	return func(c *openAIConfig) {
		c.dims = dims
	}
}

// WithAPIKey sets the OpenAI API key (overrides OPENAI_API_KEY env var).
func WithAPIKey(key string) Option {
	return func(c *openAIConfig) {
		c.apiKey = key
	}
}

// WithBaseURL sets a custom base URL (overrides OPENAI_BASE_URL env var).
func WithBaseURL(url string) Option {
	return func(c *openAIConfig) {
		c.baseURL = url
	}
}

// NewOpenAIEmbedder creates an OpenAI embedder with functional options.
func NewOpenAIEmbedder(opts ...Option) (*OpenAIEmbedder, error) {
	cfg := openAIConfig{
		model: defaultModel,
		dims:  defaultDims,
	}
	for _, opt := range opts {
		opt(&cfg)
	}

	apiKey := cfg.apiKey
	if apiKey == "" {
		apiKey = os.Getenv("OPENAI_API_KEY")
	}
	if apiKey == "" {
		return nil, errors.New("embeddings: OPENAI_API_KEY is required (set env var or use WithAPIKey)")
	}

	clientCfg := openai.DefaultConfig(apiKey)

	baseURL := cfg.baseURL
	if baseURL == "" {
		baseURL = os.Getenv("OPENAI_BASE_URL")
	}
	if baseURL != "" {
		clientCfg.BaseURL = baseURL
	}

	return &OpenAIEmbedder{
		client: openai.NewClientWithConfig(clientCfg),
		model:  cfg.model,
		dims:   cfg.dims,
	}, nil
}

// Embed generates an embedding vector for the given text.
func (e *OpenAIEmbedder) Embed(ctx context.Context, text string) ([]float32, error) {
	resp, err := e.client.CreateEmbeddings(ctx, openai.EmbeddingRequest{
		Input: []string{text},
		Model: openai.EmbeddingModel(e.model),
	})
	if err != nil {
		return nil, fmt.Errorf("embeddings: API call failed: %w", err)
	}
	if len(resp.Data) == 0 {
		return nil, errors.New("embeddings: API returned no data")
	}
	return resp.Data[0].Embedding, nil
}

// Dims returns the embedding dimensions.
func (e *OpenAIEmbedder) Dims() int {
	return e.dims
}

// Model returns the embedding model name.
func (e *OpenAIEmbedder) Model() string {
	return e.model
}
