package llm

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	openai "github.com/sashabaranov/go-openai"
)

// OpenAIProvider implements Provider using the OpenAI-compatible chat completions API.
// It covers OpenRouter, NanoGPT, and custom OpenAI endpoints by swapping the base URL.
type OpenAIProvider struct {
	client   *openai.Client
	name     string  // provider identifier
	baseURL  string  // for inspection/testing
}

// headerTransport wraps an http.RoundTripper and injects extra headers into every request.
type headerTransport struct {
	base    http.RoundTripper
	headers map[string]string
}

func (t *headerTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	for k, v := range t.headers {
		req.Header.Set(k, v)
	}
	return t.base.RoundTrip(req)
}

// NewOpenAIProvider creates an OpenAI-compatible provider from the given config.
// The config's Provider field determines the base URL:
//   - "openrouter" → https://openrouter.ai/api/v1
//   - "nanogpt"    → https://nano-gpt.com/api/v1
//   - "openai"     → CUSTOM_OPENAI_BASE_URL or https://api.openai.com/v1
//
// ExtraHeaders are injected via a custom HTTP transport.
func NewOpenAIProvider(config *LLMConfig) (*OpenAIProvider, error) {
	if config == nil {
		return nil, fmt.Errorf("config must not be nil")
	}
	if config.APIKey == "" {
		return nil, fmt.Errorf("API key is required for provider %q", config.Provider)
	}

	clientCfg := openai.DefaultConfig(config.APIKey)

	if config.BaseURL != "" {
		clientCfg.BaseURL = config.BaseURL
	}

	// Inject extra headers via a custom HTTP transport.
	if len(config.ExtraHeaders) > 0 {
		base := http.DefaultTransport
		if hc, ok := clientCfg.HTTPClient.(*http.Client); ok && hc.Transport != nil {
			base = hc.Transport
		}
		clientCfg.HTTPClient = &http.Client{
			Transport: &headerTransport{
				base:    base,
				headers: config.ExtraHeaders,
			},
		}
	}

	client := openai.NewClientWithConfig(clientCfg)

	return &OpenAIProvider{
		client:  client,
		name:    config.Provider,
		baseURL: clientCfg.BaseURL,
	}, nil
}

// Name returns the provider identifier.
func (p *OpenAIProvider) Name() string { return p.name }

// Complete sends messages and returns the text content of the first choice.
func (p *OpenAIProvider) Complete(ctx context.Context, messages []Message, config *LLMConfig) (string, error) {
	req := p.buildRequest(messages, nil, config)

	resp, err := p.client.CreateChatCompletion(ctx, req)
	if err != nil {
		return "", fmt.Errorf("openai completion failed: %w", err)
	}

	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("openai completion returned no choices")
	}

	return resp.Choices[0].Message.Content, nil
}

// CompleteWithTools sends messages with tool definitions and returns a structured response.
func (p *OpenAIProvider) CompleteWithTools(ctx context.Context, messages []Message, tools []ToolSchema, config *LLMConfig) (*ToolResponse, error) {
	oaiTools := toolSchemasToOpenAI(tools)
	req := p.buildRequest(messages, oaiTools, config)

	resp, err := p.client.CreateChatCompletion(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("openai completion with tools failed: %w", err)
	}

	if len(resp.Choices) == 0 {
		return nil, fmt.Errorf("openai completion returned no choices")
	}

	return toolResponseFromOpenAI(resp), nil
}

// buildRequest constructs a ChatCompletionRequest from internal types.
func (p *OpenAIProvider) buildRequest(messages []Message, tools []openai.Tool, config *LLMConfig) openai.ChatCompletionRequest {
	req := openai.ChatCompletionRequest{
		Model:    config.Model,
		Messages: messagesToOpenAI(messages),
	}

	if config.MaxTokens > 0 {
		req.MaxTokens = config.MaxTokens
	}

	// go-openai uses float32 for temperature/TopP.
	req.Temperature = float32(config.Temperature)

	if config.TopP > 0 && config.TopP < 1.0 {
		req.TopP = float32(config.TopP)
	}

	if len(tools) > 0 {
		req.Tools = tools
	}

	return req
}

// messagesToOpenAI converts internal Message types to go-openai ChatCompletionMessage values.
func messagesToOpenAI(msgs []Message) []openai.ChatCompletionMessage {
	out := make([]openai.ChatCompletionMessage, 0, len(msgs))

	for _, msg := range msgs {
		switch m := msg.(type) {
		case SystemMessage:
			out = append(out, openai.ChatCompletionMessage{
				Role:    openai.ChatMessageRoleSystem,
				Content: m.Content,
			})

		case UserMessage:
			if len(m.Parts) > 0 {
				parts := make([]openai.ChatMessagePart, 0, len(m.Parts))
				for _, p := range m.Parts {
					switch p.Type {
					case ContentPartText:
						parts = append(parts, openai.ChatMessagePart{
							Type: openai.ChatMessagePartTypeText,
							Text: p.Text,
						})
					case ContentPartImageBase64:
						mediaType := p.MediaType
						if mediaType == "" {
							mediaType = "image/jpeg"
						}
						dataURL := fmt.Sprintf("data:%s;base64,%s", mediaType, p.Data)
						parts = append(parts, openai.ChatMessagePart{
							Type:     openai.ChatMessagePartTypeImageURL,
							ImageURL: &openai.ChatMessageImageURL{URL: dataURL},
						})
					case ContentPartImageURL:
						parts = append(parts, openai.ChatMessagePart{
							Type:     openai.ChatMessagePartTypeImageURL,
							ImageURL: &openai.ChatMessageImageURL{URL: p.URL},
						})
					}
				}
				out = append(out, openai.ChatCompletionMessage{
					Role:         openai.ChatMessageRoleUser,
					MultiContent: parts,
				})
			} else {
				out = append(out, openai.ChatCompletionMessage{
					Role:    openai.ChatMessageRoleUser,
					Content: m.Content,
				})
			}

		case AssistantMessage:
			oaiMsg := openai.ChatCompletionMessage{
				Role: openai.ChatMessageRoleAssistant,
			}
			if m.Content != nil {
				oaiMsg.Content = *m.Content
			}
			if len(m.ToolCalls) > 0 {
				oaiMsg.ToolCalls = make([]openai.ToolCall, len(m.ToolCalls))
				for i, tc := range m.ToolCalls {
					argsJSON, err := json.Marshal(tc.Arguments)
					if err != nil {
						argsJSON = []byte("{}")
					}
					oaiMsg.ToolCalls[i] = openai.ToolCall{
						ID:   tc.ID,
						Type: openai.ToolTypeFunction,
						Function: openai.FunctionCall{
							Name:      tc.Name,
							Arguments: string(argsJSON),
						},
					}
				}
			}
			out = append(out, oaiMsg)

		case ToolResultMessage:
			out = append(out, openai.ChatCompletionMessage{
				Role:       openai.ChatMessageRoleTool,
				Content:    m.Content,
				ToolCallID: m.ToolCallID,
			})
		}
	}

	return out
}

// toolSchemasToOpenAI converts internal ToolSchema values to go-openai Tool values.
func toolSchemasToOpenAI(schemas []ToolSchema) []openai.Tool {
	tools := make([]openai.Tool, len(schemas))
	for i, s := range schemas {
		tools[i] = openai.Tool{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        s.Name,
				Description: s.Description,
				Parameters:  s.Parameters,
			},
		}
	}
	return tools
}

// toolResponseFromOpenAI converts a go-openai ChatCompletionResponse to an internal ToolResponse.
func toolResponseFromOpenAI(resp openai.ChatCompletionResponse) *ToolResponse {
	choice := resp.Choices[0]
	tr := &ToolResponse{
		StopReason: string(choice.FinishReason),
		Raw:        resp,
	}

	if len(choice.Message.ToolCalls) > 0 {
		tr.ToolCalls = make([]ToolCall, len(choice.Message.ToolCalls))
		for i, tc := range choice.Message.ToolCalls {
			var args map[string]any
			if tc.Function.Arguments != "" {
				if err := json.Unmarshal([]byte(tc.Function.Arguments), &args); err != nil {
					args = map[string]any{}
				}
			} else {
				args = map[string]any{}
			}
			tr.ToolCalls[i] = ToolCall{
				ID:           tc.ID,
				Name:         tc.Function.Name,
				Arguments:    args,
				RawArguments: tc.Function.Arguments,
			}
		}
	}

	if choice.Message.Content != "" {
		content := choice.Message.Content
		tr.Content = &content
	}

	return tr
}
