package llm

import (
	"context"
	"encoding/json"
	"fmt"

	anthropic "github.com/anthropics/anthropic-sdk-go"
	"github.com/anthropics/anthropic-sdk-go/option"
)

// AnthropicProvider implements Provider using the native Anthropic SDK.
// Supports direct Anthropic API access and proxy endpoints (e.g., clewdr)
// via custom base URL.
type AnthropicProvider struct {
	client  *anthropic.Client
	name    string
	baseURL string // for inspection/testing
}

// NewAnthropicProvider creates an Anthropic provider from the given config.
// Supports custom base URL for proxy endpoints (e.g., clewdr).
func NewAnthropicProvider(config *LLMConfig) (*AnthropicProvider, error) {
	if config == nil {
		return nil, fmt.Errorf("config must not be nil")
	}
	if config.APIKey == "" {
		return nil, fmt.Errorf("API key is required for provider %q", config.Provider)
	}

	opts := []option.RequestOption{
		option.WithAPIKey(config.APIKey),
	}

	baseURL := ""
	if config.BaseURL != "" {
		baseURL = config.BaseURL
		opts = append(opts, option.WithBaseURL(config.BaseURL))
	}

	// Inject extra headers.
	for k, v := range config.ExtraHeaders {
		opts = append(opts, option.WithHeader(k, v))
	}

	client := anthropic.NewClient(opts...)

	return &AnthropicProvider{
		client:  &client,
		name:    config.Provider,
		baseURL: baseURL,
	}, nil
}

// Name returns the provider identifier.
func (p *AnthropicProvider) Name() string { return p.name }

// Complete sends messages and returns the text content of the response.
func (p *AnthropicProvider) Complete(ctx context.Context, messages []Message, config *LLMConfig) (string, error) {
	system, anthropicMsgs := messagesToAnthropic(messages)

	params := anthropic.MessageNewParams{
		Model:     config.Model,
		Messages:  anthropicMsgs,
		MaxTokens: int64(config.MaxTokens),
	}

	if system != "" {
		params.System = []anthropic.TextBlockParam{
			{Text: system},
		}
	}

	resp, err := p.client.Messages.New(ctx, params)
	if err != nil {
		return "", fmt.Errorf("anthropic completion failed: %w", err)
	}

	// Extract text from content blocks.
	var text string
	for _, block := range resp.Content {
		if block.Type == "text" {
			text += block.Text
		}
	}

	return text, nil
}

// CompleteWithTools sends messages with tool definitions and returns a structured response.
func (p *AnthropicProvider) CompleteWithTools(ctx context.Context, messages []Message, tools []ToolSchema, config *LLMConfig) (*ToolResponse, error) {
	system, anthropicMsgs := messagesToAnthropic(messages)
	anthropicTools := toolSchemasToAnthropic(tools)

	params := anthropic.MessageNewParams{
		Model:     config.Model,
		Messages:  anthropicMsgs,
		MaxTokens: int64(config.MaxTokens),
		Tools:     anthropicTools,
	}

	if system != "" {
		params.System = []anthropic.TextBlockParam{
			{Text: system},
		}
	}

	resp, err := p.client.Messages.New(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("anthropic completion with tools failed: %w", err)
	}

	return toolResponseFromAnthropic(resp), nil
}

// messagesToAnthropic converts internal Message types to Anthropic format.
// System messages are extracted separately (Anthropic requires system as a separate param).
// ToolResultMessages are converted to user messages with tool_result content blocks.
func messagesToAnthropic(msgs []Message) (system string, anthropicMsgs []anthropic.MessageParam) {
	anthropicMsgs = make([]anthropic.MessageParam, 0, len(msgs))

	for _, msg := range msgs {
		switch m := msg.(type) {
		case SystemMessage:
			// Anthropic takes system as a separate parameter, not in messages.
			if system != "" {
				system += "\n\n"
			}
			system += m.Content

		case UserMessage:
			if len(m.Parts) > 0 {
				blocks := make([]anthropic.ContentBlockParamUnion, 0, len(m.Parts))
				for _, p := range m.Parts {
					switch p.Type {
					case ContentPartText:
						blocks = append(blocks, anthropic.NewTextBlock(p.Text))
					case ContentPartImageBase64:
						mediaType := p.MediaType
						if mediaType == "" {
							mediaType = "image/jpeg"
						}
						blocks = append(blocks, anthropic.NewImageBlockBase64(mediaType, p.Data))
					case ContentPartImageURL:
						blocks = append(blocks, anthropic.NewImageBlock(anthropic.URLImageSourceParam{
							URL: p.URL,
						}))
					}
				}
				anthropicMsgs = append(anthropicMsgs, anthropic.NewUserMessage(blocks...))
			} else {
				anthropicMsgs = append(anthropicMsgs, anthropic.NewUserMessage(
					anthropic.NewTextBlock(m.Content),
				))
			}

		case AssistantMessage:
			blocks := make([]anthropic.ContentBlockParamUnion, 0)
			if m.Content != nil && *m.Content != "" {
				blocks = append(blocks, anthropic.NewTextBlock(*m.Content))
			}
			for _, tc := range m.ToolCalls {
				blocks = append(blocks, anthropic.NewToolUseBlock(tc.ID, tc.Arguments, tc.Name))
			}
			if len(blocks) == 0 {
				// Empty assistant message — add empty text block to avoid API error.
				blocks = append(blocks, anthropic.NewTextBlock(""))
			}
			anthropicMsgs = append(anthropicMsgs, anthropic.NewAssistantMessage(blocks...))

		case ToolResultMessage:
			// Anthropic sends tool results as user messages with tool_result content blocks.
			anthropicMsgs = append(anthropicMsgs, anthropic.NewUserMessage(
				anthropic.NewToolResultBlock(m.ToolCallID, m.Content, false),
			))
		}
	}

	return system, anthropicMsgs
}

// toolSchemasToAnthropic converts internal ToolSchema values to Anthropic ToolUnionParam values.
func toolSchemasToAnthropic(schemas []ToolSchema) []anthropic.ToolUnionParam {
	tools := make([]anthropic.ToolUnionParam, len(schemas))
	for i, s := range schemas {
		// Build input schema from our generic parameters map.
		inputSchema := anthropic.ToolInputSchemaParam{
			Properties: s.Parameters["properties"],
		}
		if req, ok := s.Parameters["required"]; ok {
			if reqSlice, ok := req.([]string); ok {
				inputSchema.Required = reqSlice
			} else if reqAny, ok := req.([]any); ok {
				// Handle []any from JSON unmarshaling
				strs := make([]string, 0, len(reqAny))
				for _, v := range reqAny {
					if str, ok := v.(string); ok {
						strs = append(strs, str)
					}
				}
				inputSchema.Required = strs
			}
		}

		tool := anthropic.ToolUnionParamOfTool(inputSchema, s.Name)
		if s.Description != "" {
			tool.OfTool.Description = anthropic.Opt(s.Description)
		}
		tools[i] = tool
	}
	return tools
}

// toolResponseFromAnthropic converts an Anthropic Message response to an internal ToolResponse.
func toolResponseFromAnthropic(msg *anthropic.Message) *ToolResponse {
	tr := &ToolResponse{
		StopReason: string(msg.StopReason),
		Raw:        msg,
	}

	var textContent string
	for _, block := range msg.Content {
		switch block.Type {
		case "text":
			textContent += block.Text
		case "tool_use":
			var args map[string]any
			if len(block.Input) > 0 {
				if err := json.Unmarshal(block.Input, &args); err != nil {
					args = map[string]any{}
				}
			} else {
				args = map[string]any{}
			}
			tr.ToolCalls = append(tr.ToolCalls, ToolCall{
				ID:           block.ID,
				Name:         block.Name,
				Arguments:    args,
				RawArguments: string(block.Input),
			})
		}
	}

	if textContent != "" {
		tr.Content = &textContent
	}

	return tr
}
