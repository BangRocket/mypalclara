package discord

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/coder/websocket"
	"github.com/google/uuid"
	"github.com/rs/zerolog"

	"github.com/BangRocket/mypalclara/go/internal/config"
	"github.com/BangRocket/mypalclara/go/internal/gateway"
	"github.com/BangRocket/mypalclara/go/internal/llm"
)

const (
	defaultMaxMessages = 25
	discordMsgLimit    = 2000
	editCooldown       = 1 * time.Second
)

// tierPrefixes maps Discord message prefixes to model tiers.
var tierPrefixes = map[string]llm.ModelTier{
	"!high":   llm.TierHigh,
	"!opus":   llm.TierHigh,
	"!mid":    llm.TierMid,
	"!sonnet": llm.TierMid,
	"!low":    llm.TierLow,
	"!haiku":  llm.TierLow,
	"!fast":   llm.TierLow,
}

// pendingResponse tracks an in-flight response for streaming.
type pendingResponse struct {
	requestID       string
	channelID       string
	accumulatedText string
	toolLines       []string
	sentMessageID   string
	lastEdit        time.Time
	mu              sync.Mutex
}

// Bot is the Discord adapter that bridges Discord and the Clara gateway.
type Bot struct {
	session     *discordgo.Session
	gatewayConn *websocket.Conn
	gatewayURL  string
	nodeID      string
	log         zerolog.Logger

	// Config
	token           string
	allowedServers  map[string]bool
	allowedChannels map[string]bool
	maxMessages     int
	stopPhrases     []string

	// State
	pending   map[string]*pendingResponse // requestID -> pending
	pendingMu sync.Mutex
	cancel    context.CancelFunc
}

// Option is a functional option for configuring the Bot.
type Option func(*Bot)

// WithToken sets the Discord bot token.
func WithToken(token string) Option {
	return func(b *Bot) { b.token = token }
}

// WithGatewayURL sets the Clara gateway WebSocket URL.
func WithGatewayURL(url string) Option {
	return func(b *Bot) { b.gatewayURL = url }
}

// WithAllowedServers restricts the bot to specific Discord servers.
func WithAllowedServers(ids []string) Option {
	return func(b *Bot) {
		b.allowedServers = make(map[string]bool, len(ids))
		for _, id := range ids {
			b.allowedServers[id] = true
		}
	}
}

// WithAllowedChannels restricts the bot to specific Discord channels.
func WithAllowedChannels(ids []string) Option {
	return func(b *Bot) {
		b.allowedChannels = make(map[string]bool, len(ids))
		for _, id := range ids {
			b.allowedChannels[id] = true
		}
	}
}

// WithMaxMessages sets the maximum reply chain length.
func WithMaxMessages(n int) Option {
	return func(b *Bot) { b.maxMessages = n }
}

// WithStopPhrases sets phrases that cancel in-flight requests.
func WithStopPhrases(phrases []string) Option {
	return func(b *Bot) { b.stopPhrases = phrases }
}

// New creates a new Discord bot with the given options.
func New(opts ...Option) (*Bot, error) {
	b := &Bot{
		nodeID:      "discord-" + uuid.New().String()[:8],
		maxMessages: defaultMaxMessages,
		pending:     make(map[string]*pendingResponse),
		log:         config.NewLogger("adapters.discord"),
	}

	for _, opt := range opts {
		opt(b)
	}

	if b.token == "" {
		return nil, fmt.Errorf("discord bot token is required")
	}
	if b.gatewayURL == "" {
		return nil, fmt.Errorf("gateway URL is required")
	}

	return b, nil
}

// Start connects to both Discord and the gateway, then blocks until ctx is cancelled.
func (b *Bot) Start(ctx context.Context) error {
	ctx, b.cancel = context.WithCancel(ctx)

	// Create Discord session
	dg, err := discordgo.New("Bot " + b.token)
	if err != nil {
		return fmt.Errorf("creating discord session: %w", err)
	}
	b.session = dg

	// Set intents
	dg.Identify.Intents = discordgo.IntentsGuildMessages |
		discordgo.IntentsDirectMessages |
		discordgo.IntentsMessageContent

	// Register handlers
	dg.AddHandler(b.onMessageCreate)

	// Open Discord connection
	if err := dg.Open(); err != nil {
		return fmt.Errorf("opening discord connection: %w", err)
	}
	b.log.Info().Str("node_id", b.nodeID).Msg("Discord session opened")

	// Connect to gateway
	if err := b.connectGateway(ctx); err != nil {
		dg.Close()
		return fmt.Errorf("connecting to gateway: %w", err)
	}

	// Block until context cancelled
	<-ctx.Done()
	return nil
}

// Stop disconnects from Discord and the gateway gracefully.
func (b *Bot) Stop() error {
	if b.cancel != nil {
		b.cancel()
	}

	var errs []error
	if b.gatewayConn != nil {
		if err := b.gatewayConn.Close(websocket.StatusNormalClosure, "shutting down"); err != nil {
			errs = append(errs, fmt.Errorf("closing gateway connection: %w", err))
		}
	}
	if b.session != nil {
		if err := b.session.Close(); err != nil {
			errs = append(errs, fmt.Errorf("closing discord session: %w", err))
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("stop errors: %v", errs)
	}
	return nil
}

// connectGateway establishes a WebSocket connection to the Clara gateway
// and starts a goroutine to read responses.
func (b *Bot) connectGateway(ctx context.Context) error {
	conn, _, err := websocket.Dial(ctx, b.gatewayURL, nil)
	if err != nil {
		return fmt.Errorf("dialing gateway at %s: %w", b.gatewayURL, err)
	}
	b.gatewayConn = conn

	// Send registration
	reg := gateway.RegisterMessage{
		Type:     gateway.MsgTypeRegister,
		NodeID:   b.nodeID,
		Platform: "discord",
		Capabilities: []string{
			"streaming", "reactions", "threads", "embeds",
			"buttons", "attachments", "editing",
		},
	}
	regBytes, err := gateway.MarshalMessage(gateway.MsgTypeRegister, reg)
	if err != nil {
		return fmt.Errorf("marshaling register message: %w", err)
	}
	if err := conn.Write(ctx, websocket.MessageText, regBytes); err != nil {
		return fmt.Errorf("sending register message: %w", err)
	}
	b.log.Info().Str("node_id", b.nodeID).Msg("Sent registration to gateway")

	// Start reader goroutine
	go b.readGateway(ctx)

	return nil
}

// readGateway reads messages from the gateway WebSocket in a loop.
func (b *Bot) readGateway(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		_, data, err := b.gatewayConn.Read(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return // context cancelled, normal shutdown
			}
			b.log.Error().Err(err).Msg("Error reading from gateway")
			return
		}

		msg, err := gateway.ParseMessage(data)
		if err != nil {
			b.log.Error().Err(err).Msg("Error parsing gateway message")
			continue
		}

		b.dispatchGatewayMessage(msg)
	}
}

// dispatchGatewayMessage routes a gateway message to the appropriate handler.
func (b *Bot) dispatchGatewayMessage(msg *gateway.GatewayMessage) {
	switch msg.Type {
	case gateway.MsgTypeRegistered:
		b.log.Info().Msg("Registered with gateway")

	case gateway.MsgTypePong:
		// heartbeat response, no action needed

	case gateway.MsgTypeResponseStart:
		if rs, ok := msg.Payload.(gateway.ResponseStart); ok {
			b.onResponseStart(rs)
		}

	case gateway.MsgTypeResponseChunk:
		if rc, ok := msg.Payload.(gateway.ResponseChunk); ok {
			b.onResponseChunk(rc)
		}

	case gateway.MsgTypeResponseEnd:
		if re, ok := msg.Payload.(gateway.ResponseEnd); ok {
			b.onResponseEnd(re)
		}

	case gateway.MsgTypeToolStart:
		if ts, ok := msg.Payload.(gateway.ToolStart); ok {
			b.onToolStart(ts)
		}

	case gateway.MsgTypeToolResult:
		if tr, ok := msg.Payload.(gateway.ToolResult); ok {
			b.onToolResult(tr)
		}

	case gateway.MsgTypeError:
		if em, ok := msg.Payload.(gateway.ErrorMessage); ok {
			b.log.Error().
				Str("request_id", em.RequestID).
				Str("code", em.Code).
				Str("message", em.Message).
				Msg("Gateway error")
		}

	default:
		b.log.Debug().Str("type", msg.Type).Msg("Unhandled gateway message type")
	}
}

// onMessageCreate handles incoming Discord messages.
func (b *Bot) onMessageCreate(s *discordgo.Session, m *discordgo.MessageCreate) {
	// Ignore messages from the bot itself
	if m.Author.ID == s.State.User.ID {
		return
	}

	// Ignore bot messages
	if m.Author.Bot {
		return
	}

	// Check server allowlist
	if len(b.allowedServers) > 0 && m.GuildID != "" {
		if !b.allowedServers[m.GuildID] {
			return
		}
	}

	// Check channel allowlist
	if !b.isChannelAllowed(m.ChannelID) {
		// Also check if it's a DM (no guild = DM)
		if m.GuildID != "" {
			return
		}
	}

	content := m.Content

	// Check for stop phrases
	if b.isStopPhrase(content) {
		b.handleStopPhrase(m)
		return
	}

	// Parse tier prefix
	tier, content := ParseTierPrefix(content)

	if strings.TrimSpace(content) == "" {
		return
	}

	// Build reply chain
	replyChain := b.buildReplyChain(s, m.Message)

	// Determine channel type
	channelType := "server"
	if m.GuildID == "" {
		channelType = "dm"
	}

	// Build channel info
	channelInfo := gateway.ChannelInfo{
		ID:      m.ChannelID,
		Type:    channelType,
		GuildID: m.GuildID,
	}

	// Try to get channel name and guild name
	if ch, err := s.Channel(m.ChannelID); err == nil {
		channelInfo.Name = ch.Name
	}
	if m.GuildID != "" {
		if guild, err := s.Guild(m.GuildID); err == nil {
			channelInfo.GuildName = guild.Name
		}
	}

	// Build user info
	userInfo := gateway.UserInfo{
		ID:          "discord-" + m.Author.ID,
		PlatformID:  m.Author.ID,
		Name:        m.Author.Username,
		DisplayName: m.Author.GlobalName,
	}

	// Generate request ID
	requestID := uuid.New().String()

	// Build the message request
	req := gateway.MessageRequest{
		Type:       gateway.MsgTypeMessage,
		ID:         requestID,
		User:       userInfo,
		Channel:    channelInfo,
		Content:    content,
		ReplyChain: replyChain,
	}
	if tier != "" {
		req.TierOverride = string(tier)
	}

	// Track the pending response
	b.pendingMu.Lock()
	b.pending[requestID] = &pendingResponse{
		requestID: requestID,
		channelID: m.ChannelID,
	}
	b.pendingMu.Unlock()

	// Send typing indicator
	_ = s.ChannelTyping(m.ChannelID)

	// Send to gateway
	reqBytes, err := gateway.MarshalMessage(gateway.MsgTypeMessage, req)
	if err != nil {
		b.log.Error().Err(err).Msg("Failed to marshal message request")
		return
	}

	ctx := context.Background()
	if err := b.gatewayConn.Write(ctx, websocket.MessageText, reqBytes); err != nil {
		b.log.Error().Err(err).Msg("Failed to send message to gateway")
		return
	}

	b.log.Debug().
		Str("request_id", requestID).
		Str("user", m.Author.Username).
		Str("content_preview", truncate(content, 50)).
		Msg("Sent message to gateway")
}

// isChannelAllowed checks if a channel is in the allowlist.
// Returns true if no allowlist is configured (all channels allowed).
func (b *Bot) isChannelAllowed(channelID string) bool {
	if len(b.allowedChannels) == 0 {
		return true
	}
	return b.allowedChannels[channelID]
}

// isStopPhrase checks if content matches any configured stop phrase.
func (b *Bot) isStopPhrase(content string) bool {
	lower := strings.ToLower(strings.TrimSpace(content))
	for _, phrase := range b.stopPhrases {
		if strings.ToLower(phrase) == lower {
			return true
		}
	}
	return false
}

// handleStopPhrase cancels any pending requests in the message's channel.
func (b *Bot) handleStopPhrase(m *discordgo.MessageCreate) {
	b.pendingMu.Lock()
	var toCancel []string
	for id, pr := range b.pending {
		if pr.channelID == m.ChannelID {
			toCancel = append(toCancel, id)
		}
	}
	b.pendingMu.Unlock()

	for _, id := range toCancel {
		cancel := gateway.CancelMessage{
			Type:      gateway.MsgTypeCancel,
			RequestID: id,
			Reason:    "stop phrase",
		}
		cancelBytes, err := gateway.MarshalMessage(gateway.MsgTypeCancel, cancel)
		if err != nil {
			continue
		}
		_ = b.gatewayConn.Write(context.Background(), websocket.MessageText, cancelBytes)
	}

	_ = b.session.MessageReactionAdd(m.ChannelID, m.ID, "🛑")
}

// ParseTierPrefix extracts a model tier prefix from message content.
// Returns the tier (empty string if none) and the remaining content.
func ParseTierPrefix(content string) (llm.ModelTier, string) {
	trimmed := strings.TrimSpace(content)
	lower := strings.ToLower(trimmed)
	for prefix, tier := range tierPrefixes {
		if !strings.HasPrefix(lower, prefix) {
			continue
		}
		// Must be followed by space or end of string (word boundary).
		rest := trimmed[len(prefix):]
		if rest != "" && rest[0] != ' ' {
			continue
		}
		return tier, strings.TrimSpace(rest)
	}
	return "", content
}

// buildReplyChain walks the reply reference chain up to maxMessages.
// Returns a slice of message dicts with role, content, user_name, timestamp.
func (b *Bot) buildReplyChain(s *discordgo.Session, msg *discordgo.Message) []map[string]any {
	if msg.ReferencedMessage == nil {
		return nil
	}

	var chain []map[string]any
	current := msg.ReferencedMessage

	for i := 0; i < b.maxMessages && current != nil; i++ {
		role := "user"
		if current.Author != nil && s.State != nil && s.State.User != nil && current.Author.ID == s.State.User.ID {
			role = "assistant"
		}

		entry := map[string]any{
			"role":    role,
			"content": current.Content,
		}
		if current.Author != nil {
			entry["user_name"] = current.Author.Username
		}
		if !current.Timestamp.IsZero() {
			entry["timestamp"] = current.Timestamp.Format(time.RFC3339)
		}

		// Prepend (oldest first)
		chain = append([]map[string]any{entry}, chain...)

		// Walk to next parent
		if current.ReferencedMessage != nil {
			current = current.ReferencedMessage
		} else if current.MessageReference != nil {
			// Fetch the referenced message
			ref, err := s.ChannelMessage(current.MessageReference.ChannelID, current.MessageReference.MessageID)
			if err != nil {
				break
			}
			current = ref
		} else {
			break
		}
	}

	return chain
}

// onResponseStart handles the start of a gateway response.
func (b *Bot) onResponseStart(rs gateway.ResponseStart) {
	b.pendingMu.Lock()
	pr, ok := b.pending[rs.RequestID]
	b.pendingMu.Unlock()
	if !ok {
		return
	}

	// Send typing indicator
	_ = b.session.ChannelTyping(pr.channelID)
	b.log.Debug().Str("request_id", rs.RequestID).Msg("Response started")
}

// onResponseChunk handles a streaming response chunk.
func (b *Bot) onResponseChunk(rc gateway.ResponseChunk) {
	b.pendingMu.Lock()
	pr, ok := b.pending[rc.RequestID]
	b.pendingMu.Unlock()
	if !ok {
		return
	}

	pr.mu.Lock()
	defer pr.mu.Unlock()

	if rc.Accumulated != "" {
		pr.accumulatedText = rc.Accumulated
	} else {
		pr.accumulatedText += rc.Chunk
	}

	// Rate-limit edits
	if time.Since(pr.lastEdit) < editCooldown && pr.sentMessageID != "" {
		return
	}

	displayText := b.buildDisplayText(pr)

	if pr.sentMessageID == "" {
		// Send initial message
		msg, err := b.session.ChannelMessageSend(pr.channelID, truncateForDiscord(displayText))
		if err != nil {
			b.log.Error().Err(err).Msg("Failed to send streaming message")
			return
		}
		pr.sentMessageID = msg.ID
	} else {
		// Edit existing message
		_, err := b.session.ChannelMessageEdit(pr.channelID, pr.sentMessageID, truncateForDiscord(displayText))
		if err != nil {
			b.log.Error().Err(err).Msg("Failed to edit streaming message")
		}
	}
	pr.lastEdit = time.Now()
}

// onResponseEnd handles the completion of a gateway response.
func (b *Bot) onResponseEnd(re gateway.ResponseEnd) {
	b.pendingMu.Lock()
	pr, ok := b.pending[re.RequestID]
	delete(b.pending, re.RequestID)
	b.pendingMu.Unlock()
	if !ok {
		return
	}

	pr.mu.Lock()
	defer pr.mu.Unlock()

	fullText := re.FullText

	// Process special markers in the response
	b.processSpecialMarkers(pr, fullText)

	// Final edit or send
	if pr.sentMessageID != "" {
		_, err := b.session.ChannelMessageEdit(pr.channelID, pr.sentMessageID, truncateForDiscord(fullText))
		if err != nil {
			b.log.Error().Err(err).Msg("Failed to send final edit")
		}
	} else if fullText != "" {
		_, err := b.session.ChannelMessageSend(pr.channelID, truncateForDiscord(fullText))
		if err != nil {
			b.log.Error().Err(err).Msg("Failed to send final message")
		}
	}

	b.log.Debug().
		Str("request_id", re.RequestID).
		Int("tool_count", re.ToolCount).
		Msg("Response complete")
}

// onToolStart handles tool execution start notifications.
func (b *Bot) onToolStart(ts gateway.ToolStart) {
	b.pendingMu.Lock()
	pr, ok := b.pending[ts.RequestID]
	b.pendingMu.Unlock()
	if !ok {
		return
	}

	pr.mu.Lock()
	defer pr.mu.Unlock()

	emoji := ts.Emoji
	if emoji == "" {
		emoji = "⚙️"
	}
	line := fmt.Sprintf("%s Using **%s**...", emoji, ts.ToolName)
	pr.toolLines = append(pr.toolLines, line)
}

// onToolResult handles tool execution result notifications.
func (b *Bot) onToolResult(tr gateway.ToolResult) {
	b.pendingMu.Lock()
	pr, ok := b.pending[tr.RequestID]
	b.pendingMu.Unlock()
	if !ok {
		return
	}

	pr.mu.Lock()
	defer pr.mu.Unlock()

	status := "✅"
	if !tr.Success {
		status = "❌"
	}

	// Update the last tool line with result
	if len(pr.toolLines) > 0 {
		last := len(pr.toolLines) - 1
		pr.toolLines[last] = fmt.Sprintf("%s **%s** %s", status, tr.ToolName, statusSuffix(tr))
	}
}

// processSpecialMarkers handles Discord-specific tool result markers in the response text.
func (b *Bot) processSpecialMarkers(pr *pendingResponse, text string) {
	lines := strings.Split(text, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)

		switch {
		case strings.HasPrefix(line, "__REACTION__:"):
			emoji := strings.TrimPrefix(line, "__REACTION__:")
			if pr.sentMessageID != "" {
				_ = b.session.MessageReactionAdd(pr.channelID, pr.sentMessageID, strings.TrimSpace(emoji))
			}

		case strings.HasPrefix(line, "__EMBED__:"):
			jsonStr := strings.TrimPrefix(line, "__EMBED__:")
			var embed discordgo.MessageEmbed
			if err := json.Unmarshal([]byte(jsonStr), &embed); err == nil {
				_, _ = b.session.ChannelMessageSendEmbed(pr.channelID, &embed)
			}

		case strings.HasPrefix(line, "__THREAD__:"):
			parts := strings.SplitN(strings.TrimPrefix(line, "__THREAD__:"), ":", 2)
			if len(parts) >= 1 && pr.sentMessageID != "" {
				archiveDuration := 60 // default 1 hour
				if len(parts) >= 2 {
					if d := parseArchiveDuration(parts[1]); d > 0 {
						archiveDuration = d
					}
				}
				_, _ = b.session.MessageThreadStartComplex(pr.channelID, pr.sentMessageID, &discordgo.ThreadStart{
					Name:                parts[0],
					AutoArchiveDuration: archiveDuration,
				})
			}

		case strings.HasPrefix(line, "__BUTTONS__:"):
			// Button components are handled via ResponseEnd.Components
			// This marker is for backward compatibility
		}
	}
}

// buildDisplayText constructs the current display text including tool status lines.
func (b *Bot) buildDisplayText(pr *pendingResponse) string {
	var parts []string
	if len(pr.toolLines) > 0 {
		parts = append(parts, strings.Join(pr.toolLines, "\n"))
	}
	if pr.accumulatedText != "" {
		parts = append(parts, pr.accumulatedText)
	}
	if len(parts) == 0 {
		return "..."
	}
	return strings.Join(parts, "\n\n")
}

// truncateForDiscord ensures text fits within Discord's message limit.
func truncateForDiscord(text string) string {
	if len(text) <= discordMsgLimit {
		return text
	}
	return text[:discordMsgLimit-3] + "..."
}

// truncate shortens a string for logging.
func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "..."
}

// statusSuffix generates a brief status suffix for a tool result.
func statusSuffix(tr gateway.ToolResult) string {
	if tr.DurationMs != nil {
		return fmt.Sprintf("(%dms)", *tr.DurationMs)
	}
	return ""
}

// parseArchiveDuration converts a string archive duration to minutes.
func parseArchiveDuration(s string) int {
	s = strings.TrimSpace(strings.ToLower(s))
	switch s {
	case "60", "1h", "1hour":
		return 60
	case "1440", "24h", "1day", "1d":
		return 1440
	case "4320", "3d", "3days":
		return 4320
	case "10080", "7d", "7days", "1w", "1week":
		return 10080
	default:
		return 0
	}
}
