// Package llm provides typed message formats for Clara's internal message pipeline.
//
// Defines MyPalClara's own message types. Everything inside the pipeline
// speaks []Message. Providers translate at their boundary.
package llm

import "fmt"

// ContentPartType enumerates the kinds of content in a multimodal message.
type ContentPartType string

const (
	ContentPartText        ContentPartType = "text"
	ContentPartImageBase64 ContentPartType = "image_base64"
	ContentPartImageURL    ContentPartType = "image_url"
)

// ContentPart is a single part of a multimodal user message.
type ContentPart struct {
	Type      ContentPartType
	Text      string // when Type is ContentPartText
	MediaType string // MIME type for images, e.g. "image/png"
	Data      string // base64-encoded image data (ContentPartImageBase64)
	URL       string // HTTP URL for the image (ContentPartImageURL)
}

// ToOpenAI serializes the part to OpenAI content-part format.
func (p ContentPart) ToOpenAI() map[string]any {
	switch p.Type {
	case ContentPartText:
		return map[string]any{"type": "text", "text": p.Text}
	case ContentPartImageBase64:
		mediaType := p.MediaType
		if mediaType == "" {
			mediaType = "image/jpeg"
		}
		dataURL := fmt.Sprintf("data:%s;base64,%s", mediaType, p.Data)
		return map[string]any{
			"type":      "image_url",
			"image_url": map[string]any{"url": dataURL},
		}
	case ContentPartImageURL:
		return map[string]any{
			"type":      "image_url",
			"image_url": map[string]any{"url": p.URL},
		}
	default:
		return map[string]any{"type": "text", "text": ""}
	}
}

// Message is the interface all message types implement.
type Message interface {
	// Role returns the message role string ("system", "user", "assistant", "tool").
	Role() string
	// ToOpenAI serializes the message to an OpenAI-format dict.
	ToOpenAI() map[string]any
}

// SystemMessage is a system-level instruction message.
type SystemMessage struct {
	Content string
}

func (m SystemMessage) Role() string        { return "system" }
func (m SystemMessage) ToOpenAI() map[string]any {
	return map[string]any{"role": "system", "content": m.Content}
}

// UserMessage is a user-sent message, optionally multimodal.
// For plain text, set Content and leave Parts empty.
// For multimodal (text + images), populate Parts.
type UserMessage struct {
	Content string
	Parts   []ContentPart
}

func (m UserMessage) Role() string { return "user" }
func (m UserMessage) ToOpenAI() map[string]any {
	if len(m.Parts) > 0 {
		parts := make([]map[string]any, len(m.Parts))
		for i, p := range m.Parts {
			parts[i] = p.ToOpenAI()
		}
		return map[string]any{"role": "user", "content": parts}
	}
	return map[string]any{"role": "user", "content": m.Content}
}

// AssistantMessage is an assistant response, optionally with tool calls.
// Content is a pointer to allow nil (matches Python's str | None).
type AssistantMessage struct {
	Content   *string
	ToolCalls []ToolCall
}

func (m AssistantMessage) Role() string { return "assistant" }
func (m AssistantMessage) ToOpenAI() map[string]any {
	var content any
	if m.Content != nil {
		content = m.Content
	}
	result := map[string]any{
		"role":    "assistant",
		"content": content,
	}
	if len(m.ToolCalls) > 0 {
		tcs := make([]map[string]any, len(m.ToolCalls))
		for i, tc := range m.ToolCalls {
			tcs[i] = tc.ToOpenAIFormat()
		}
		result["tool_calls"] = tcs
	}
	return result
}

// ToolResultMessage is the result of executing a tool call.
type ToolResultMessage struct {
	ToolCallID string
	Content    string
}

func (m ToolResultMessage) Role() string { return "tool" }
func (m ToolResultMessage) ToOpenAI() map[string]any {
	return map[string]any{
		"role":         "tool",
		"tool_call_id": m.ToolCallID,
		"content":      m.Content,
	}
}

// MessageFromDict creates a Message from an OpenAI-format dict.
// Dispatches on the "role" key. Returns error for unknown roles.
func MessageFromDict(d map[string]any) (Message, error) {
	role, _ := d["role"].(string)

	switch role {
	case "system":
		content, _ := d["content"].(string)
		return SystemMessage{Content: content}, nil

	case "user":
		switch c := d["content"].(type) {
		case string:
			return UserMessage{Content: c}, nil
		case []any:
			parts := make([]ContentPart, 0, len(c))
			var textParts []string
			for _, raw := range c {
				pd, ok := raw.(map[string]any)
				if !ok {
					continue
				}
				part := contentPartFromDict(pd)
				parts = append(parts, part)
				if part.Type == ContentPartText && part.Text != "" {
					textParts = append(textParts, part.Text)
				}
			}
			text := ""
			for i, t := range textParts {
				if i > 0 {
					text += " "
				}
				text += t
			}
			return UserMessage{Content: text, Parts: parts}, nil
		default:
			return UserMessage{Content: fmt.Sprintf("%v", c)}, nil
		}

	case "assistant":
		var content *string
		if c, ok := d["content"]; ok && c != nil {
			s, _ := c.(string)
			content = &s
		}
		var toolCalls []ToolCall
		if tcs, ok := d["tool_calls"].([]any); ok {
			for _, raw := range tcs {
				if tc, ok := raw.(map[string]any); ok {
					toolCalls = append(toolCalls, ToolCallFromOpenAI(tc))
				}
			}
		}
		return AssistantMessage{Content: content, ToolCalls: toolCalls}, nil

	case "tool":
		toolCallID, _ := d["tool_call_id"].(string)
		content, _ := d["content"].(string)
		return ToolResultMessage{ToolCallID: toolCallID, Content: content}, nil

	default:
		return nil, fmt.Errorf("unknown message role: %q", role)
	}
}

// MessagesFromDicts converts a slice of OpenAI-format dicts to typed Messages.
func MessagesFromDicts(ds []map[string]any) ([]Message, error) {
	msgs := make([]Message, 0, len(ds))
	for _, d := range ds {
		m, err := MessageFromDict(d)
		if err != nil {
			return nil, err
		}
		msgs = append(msgs, m)
	}
	return msgs, nil
}

// contentPartFromDict creates a ContentPart from an OpenAI content-part dict.
func contentPartFromDict(d map[string]any) ContentPart {
	partType, _ := d["type"].(string)

	switch partType {
	case "text":
		text, _ := d["text"].(string)
		return ContentPart{Type: ContentPartText, Text: text}
	case "image_url":
		imageURL := ""
		if iu, ok := d["image_url"].(map[string]any); ok {
			imageURL, _ = iu["url"].(string)
		}
		// Check if it's a data URL (base64-encoded)
		if len(imageURL) > 5 && imageURL[:5] == "data:" {
			// Parse "data:image/png;base64,AAAA..."
			rest := imageURL[5:]
			var mediaType, base64Data string
			for i, ch := range rest {
				if ch == ';' {
					mediaType = rest[:i]
					// Find the comma after ";base64,"
					commaRest := rest[i+1:]
					for j, ch2 := range commaRest {
						if ch2 == ',' {
							base64Data = commaRest[j+1:]
							break
						}
					}
					break
				}
			}
			if mediaType != "" {
				return ContentPart{
					Type:      ContentPartImageBase64,
					MediaType: mediaType,
					Data:      base64Data,
				}
			}
		}
		return ContentPart{Type: ContentPartImageURL, URL: imageURL}
	default:
		return ContentPart{Type: ContentPartText, Text: fmt.Sprintf("%v", d)}
	}
}
