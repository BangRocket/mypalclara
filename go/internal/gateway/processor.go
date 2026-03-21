// Package gateway — processor.go implements the MessageProcessor that bridges
// incoming requests to memory, LLM orchestration, and tool execution.
//
// Ported from mypalclara/gateway/message_processor.py.
package gateway

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"github.com/BangRocket/mypalclara/go/internal/llm"
	"github.com/BangRocket/mypalclara/go/internal/memory"

	gatewaytools "github.com/BangRocket/mypalclara/go/internal/gateway/tools"
)

const (
	// recentMessageLimit is the number of recent messages to fetch from session history.
	recentMessageLimit = 20
)

// MessageProcessor implements the Processor interface.
// It orchestrates session management, memory retrieval, prompt building,
// LLM calls with tool execution, and response delivery.
type MessageProcessor struct {
	memoryManager *memory.Manager
	orchestrator  *Orchestrator
	toolExecutor  *gatewaytools.Executor
	compactor     *Compactor
	logger        zerolog.Logger
}

// NewMessageProcessor creates a MessageProcessor wired to the given memory manager
// and LLM provider.
func NewMessageProcessor(mm *memory.Manager, provider llm.Provider) *MessageProcessor {
	executor := gatewaytools.NewExecutor()
	orchestrator := NewOrchestrator(provider, executor)

	return &MessageProcessor{
		memoryManager: mm,
		orchestrator:  orchestrator,
		toolExecutor:  executor,
		compactor:     NewCompactor(),
		logger:        log.With().Str("component", "processor").Logger(),
	}
}

// SetLogger replaces the processor's logger.
func (p *MessageProcessor) SetLogger(logger zerolog.Logger) {
	p.logger = logger
}

// ToolExecutor returns the underlying tool executor for registering tool handlers.
func (p *MessageProcessor) ToolExecutor() *gatewaytools.Executor {
	return p.toolExecutor
}

// Process handles a message request end-to-end.
//
// Flow:
//  1. Get/create session via memory manager
//  2. Fetch recent messages from session
//  3. Fetch memory context (user + project memories)
//  4. Build prompt via memory manager
//  5. Compact if needed
//  6. Send ResponseStart
//  7. Run orchestrator.GenerateWithTools, forwarding events to send
//  8. Store user message + assistant reply
//  9. Send ResponseEnd
//  10. Background: add memories from conversation
func (p *MessageProcessor) Process(ctx context.Context, req *MessageRequest, send func(msg any) error) error {
	reqLog := p.logger.With().
		Str("request_id", req.ID).
		Str("user_id", req.User.ID).
		Str("channel_id", req.Channel.ID).
		Logger()

	reqLog.Info().Str("content_preview", truncate(req.Content, 80)).Msg("processing message")

	// 1. Get or create session.
	contextID := req.Channel.ID
	projectID := "default"
	if md, ok := req.Metadata["project_id"].(string); ok && md != "" {
		projectID = md
	}

	session, err := p.memoryManager.GetOrCreateSession(ctx, req.User.ID, contextID, projectID)
	if err != nil {
		return fmt.Errorf("get/create session: %w", err)
	}
	reqLog = reqLog.With().Str("session_id", session.ID).Logger()

	// 2. Fetch recent messages from session.
	recentMsgs, err := p.memoryManager.GetRecentMessages(ctx, session.ID, recentMessageLimit)
	if err != nil {
		reqLog.Warn().Err(err).Msg("failed to fetch recent messages, continuing with empty history")
		recentMsgs = nil
	}

	// 3. Fetch memory context.
	memCtx, err := p.memoryManager.FetchContext(ctx, req.User.ID, req.Content, memory.FetchOptions{
		ProjectID:    projectID,
		IsDM:         req.Channel.Type == "dm",
		PrivacyScope: privacyScope(req.Channel.Type),
	})
	if err != nil {
		reqLog.Warn().Err(err).Msg("failed to fetch memory context, continuing without memories")
		memCtx = &memory.MemoryContext{}
	}

	// 4. Build prompt.
	messages := p.memoryManager.BuildPrompt(ctx, memCtx, memory.PromptOptions{
		RecentMessages: recentMsgs,
		UserMessage:    req.Content,
		SessionSummary: session.SessionSummary,
		UserID:         req.User.ID,
		PrivacyScope:   privacyScope(req.Channel.Type),
	})

	// 5. Compact if context is too large.
	compactResult := p.compactor.CompactIfNeeded(messages, 128000) // Default 128k budget
	if compactResult.WasCompacted {
		reqLog.Info().Int("tokens_saved", compactResult.TokensSaved).Msg("context compacted")
	}
	messages = compactResult.Messages

	// 6. Get tools (empty for now — tools registered externally).
	var tools []llm.ToolSchema

	// 7. Send ResponseStart.
	responseID := uuid.New().String()
	tier := req.TierOverride

	startMsg, _ := MarshalMessage(MsgTypeResponseStart, ResponseStart{
		Type:      MsgTypeResponseStart,
		ID:        responseID,
		RequestID: req.ID,
		ModelTier: tier,
	})
	if err := send(startMsg); err != nil {
		return fmt.Errorf("send response_start: %w", err)
	}

	// 8. Run orchestrator with tool loop.
	var fullText string
	var totalToolCount int
	var orchestratorErr error

	fullText, orchestratorErr = p.orchestrator.GenerateWithTools(
		ctx,
		messages,
		tools,
		req.User.ID,
		tier,
		func(event Event) {
			switch event.Type {
			case "tool_start":
				data, _ := MarshalMessage(MsgTypeToolStart, ToolStart{
					Type:        MsgTypeToolStart,
					ID:          uuid.New().String(),
					RequestID:   req.ID,
					ToolName:    event.ToolName,
					Step:        event.Step,
					Arguments:   event.Arguments,
				})
				_ = send(data)

			case "tool_result":
				data, _ := MarshalMessage(MsgTypeToolResult, ToolResult{
					Type:          MsgTypeToolResult,
					ID:            uuid.New().String(),
					RequestID:     req.ID,
					ToolName:      event.ToolName,
					Success:       event.Success,
					OutputPreview: event.Preview,
				})
				_ = send(data)

			case "chunk":
				data, _ := MarshalMessage(MsgTypeResponseChunk, ResponseChunk{
					Type:      MsgTypeResponseChunk,
					ID:        uuid.New().String(),
					RequestID: req.ID,
					Chunk:     event.Text,
				})
				_ = send(data)

			case "complete":
				totalToolCount = event.ToolCount
			}
		},
	)

	if orchestratorErr != nil {
		return fmt.Errorf("orchestrator: %w", orchestratorErr)
	}

	// 9. Store user message and assistant reply.
	if storeErr := p.memoryManager.StoreMessage(ctx, session.ID, req.User.ID, "user", req.Content); storeErr != nil {
		reqLog.Warn().Err(storeErr).Msg("failed to store user message")
	}
	if fullText != "" {
		if storeErr := p.memoryManager.StoreMessage(ctx, session.ID, "assistant", "assistant", fullText); storeErr != nil {
			reqLog.Warn().Err(storeErr).Msg("failed to store assistant message")
		}
	}

	// 10. Send ResponseEnd.
	endMsg, _ := MarshalMessage(MsgTypeResponseEnd, ResponseEnd{
		Type:      MsgTypeResponseEnd,
		ID:        responseID,
		RequestID: req.ID,
		FullText:  fullText,
		ToolCount: totalToolCount,
	})
	if err := send(endMsg); err != nil {
		return fmt.Errorf("send response_end: %w", err)
	}

	// 11. Background: extract and store memories.
	go func() {
		bgCtx := context.Background()
		addErr := p.memoryManager.AddFromConversation(bgCtx, memory.WriteOptions{
			UserID:         req.User.ID,
			ProjectID:      projectID,
			RecentMessages: recentMsgs,
			UserMessage:    req.Content,
			AssistantReply: fullText,
			IsDM:           req.Channel.Type == "dm",
		})
		if addErr != nil {
			reqLog.Warn().Err(addErr).Msg("background memory extraction failed")
		}
	}()

	reqLog.Info().
		Int("tool_count", totalToolCount).
		Int("response_len", len(fullText)).
		Msg("message processed")

	return nil
}

// --- Helpers ---

// privacyScope returns the privacy scope based on channel type.
func privacyScope(channelType string) string {
	if channelType == "dm" {
		return "full"
	}
	return "public_only"
}

// truncate shortens s to maxLen, appending "..." if truncated.
func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
