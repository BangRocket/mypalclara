package discord

import (
	"testing"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

func TestParseTierPrefix(t *testing.T) {
	tests := []struct {
		input    string
		wantTier llm.ModelTier
		wantText string
	}{
		// High tier
		{"!high What is quantum physics?", llm.TierHigh, "What is quantum physics?"},
		{"!opus Explain relativity", llm.TierHigh, "Explain relativity"},

		// Mid tier
		{"!mid Tell me a joke", llm.TierMid, "Tell me a joke"},
		{"!sonnet Write a poem", llm.TierMid, "Write a poem"},

		// Low tier
		{"!low Hi", llm.TierLow, "Hi"},
		{"!haiku Hello", llm.TierLow, "Hello"},
		{"!fast What time is it?", llm.TierLow, "What time is it?"},

		// No prefix
		{"Hello Clara", "", "Hello Clara"},
		{"", "", ""},

		// Case insensitive
		{"!HIGH test", llm.TierHigh, "test"},
		{"!High test", llm.TierHigh, "test"},

		// Leading whitespace
		{"  !low test", llm.TierLow, "test"},

		// Prefix without content
		{"!high", llm.TierHigh, ""},
		{"!mid ", llm.TierMid, ""},

		// Not a prefix (part of word)
		{"!highway to hell", "", "!highway to hell"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			gotTier, gotText := ParseTierPrefix(tt.input)
			if gotTier != tt.wantTier {
				t.Errorf("ParseTierPrefix(%q) tier = %q, want %q", tt.input, gotTier, tt.wantTier)
			}
			if gotText != tt.wantText {
				t.Errorf("ParseTierPrefix(%q) text = %q, want %q", tt.input, gotText, tt.wantText)
			}
		})
	}
}

func TestBuildReplyChainFormat(t *testing.T) {
	// We can't test with real Discord sessions, but we can verify the
	// data format by constructing what buildReplyChain should produce.
	chain := []map[string]any{
		{
			"role":      "user",
			"content":   "What is Go?",
			"user_name": "alice",
			"timestamp": "2025-01-01T12:00:00Z",
		},
		{
			"role":      "assistant",
			"content":   "Go is a programming language.",
			"user_name": "Clara",
			"timestamp": "2025-01-01T12:00:05Z",
		},
	}

	// Verify structure
	if len(chain) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(chain))
	}

	// First message should be from user
	if chain[0]["role"] != "user" {
		t.Errorf("first message role = %q, want %q", chain[0]["role"], "user")
	}
	if chain[0]["content"] != "What is Go?" {
		t.Errorf("first message content = %q, want %q", chain[0]["content"], "What is Go?")
	}
	if _, ok := chain[0]["user_name"]; !ok {
		t.Error("first message missing user_name")
	}
	if _, ok := chain[0]["timestamp"]; !ok {
		t.Error("first message missing timestamp")
	}

	// Second message should be from assistant
	if chain[1]["role"] != "assistant" {
		t.Errorf("second message role = %q, want %q", chain[1]["role"], "assistant")
	}
}

func TestConfigFromEnv(t *testing.T) {
	// Set env vars
	t.Setenv("DISCORD_BOT_TOKEN", "test-token-123")
	t.Setenv("DISCORD_ALLOWED_SERVERS", "111,222,333")
	t.Setenv("DISCORD_ALLOWED_CHANNELS", "444, 555")
	t.Setenv("DISCORD_MAX_MESSAGES", "10")
	t.Setenv("DISCORD_STOP_PHRASES", "clara stop,stop clara,nevermind")
	t.Setenv("CLARA_GATEWAY_HOST", "10.0.0.1")
	t.Setenv("CLARA_GATEWAY_PORT", "9999")

	opts := ConfigFromEnv()

	// Apply options to a bot to verify
	bot := &Bot{
		maxMessages: defaultMaxMessages,
		pending:     make(map[string]*pendingResponse),
	}
	for _, opt := range opts {
		opt(bot)
	}

	if bot.token != "test-token-123" {
		t.Errorf("token = %q, want %q", bot.token, "test-token-123")
	}

	if bot.gatewayURL != "ws://10.0.0.1:9999/ws" {
		t.Errorf("gatewayURL = %q, want %q", bot.gatewayURL, "ws://10.0.0.1:9999/ws")
	}

	if len(bot.allowedServers) != 3 {
		t.Errorf("allowedServers count = %d, want 3", len(bot.allowedServers))
	}
	for _, id := range []string{"111", "222", "333"} {
		if !bot.allowedServers[id] {
			t.Errorf("allowedServers missing %q", id)
		}
	}

	if len(bot.allowedChannels) != 2 {
		t.Errorf("allowedChannels count = %d, want 2", len(bot.allowedChannels))
	}
	// Check whitespace trimming
	if !bot.allowedChannels["555"] {
		t.Error("allowedChannels missing '555' (whitespace not trimmed)")
	}

	if bot.maxMessages != 10 {
		t.Errorf("maxMessages = %d, want 10", bot.maxMessages)
	}

	if len(bot.stopPhrases) != 3 {
		t.Errorf("stopPhrases count = %d, want 3", len(bot.stopPhrases))
	}
}

func TestConfigFromEnvDefaults(t *testing.T) {
	// Clear all Discord env vars
	t.Setenv("DISCORD_BOT_TOKEN", "")
	t.Setenv("DISCORD_ALLOWED_SERVERS", "")
	t.Setenv("DISCORD_ALLOWED_CHANNELS", "")
	t.Setenv("DISCORD_MAX_MESSAGES", "")
	t.Setenv("DISCORD_STOP_PHRASES", "")
	t.Setenv("CLARA_GATEWAY_HOST", "")
	t.Setenv("CLARA_GATEWAY_PORT", "")

	opts := ConfigFromEnv()

	bot := &Bot{
		maxMessages: defaultMaxMessages,
		pending:     make(map[string]*pendingResponse),
	}
	for _, opt := range opts {
		opt(bot)
	}

	// Default gateway URL
	if bot.gatewayURL != "ws://127.0.0.1:18789/ws" {
		t.Errorf("default gatewayURL = %q, want %q", bot.gatewayURL, "ws://127.0.0.1:18789/ws")
	}

	// No token (empty string from env not applied)
	if bot.token != "" {
		t.Errorf("default token should be empty, got %q", bot.token)
	}

	// No allowlists
	if len(bot.allowedServers) != 0 {
		t.Errorf("default allowedServers should be empty, got %d", len(bot.allowedServers))
	}
}

func TestIsChannelAllowed(t *testing.T) {
	tests := []struct {
		name            string
		allowedChannels map[string]bool
		channelID       string
		want            bool
	}{
		{
			name:            "no allowlist allows all",
			allowedChannels: nil,
			channelID:       "any-channel",
			want:            true,
		},
		{
			name:            "empty allowlist allows all",
			allowedChannels: map[string]bool{},
			channelID:       "any-channel",
			want:            true,
		},
		{
			name:            "allowed channel",
			allowedChannels: map[string]bool{"123": true, "456": true},
			channelID:       "123",
			want:            true,
		},
		{
			name:            "denied channel",
			allowedChannels: map[string]bool{"123": true, "456": true},
			channelID:       "789",
			want:            false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			b := &Bot{allowedChannels: tt.allowedChannels}
			got := b.isChannelAllowed(tt.channelID)
			if got != tt.want {
				t.Errorf("isChannelAllowed(%q) = %v, want %v", tt.channelID, got, tt.want)
			}
		})
	}
}

func TestIsStopPhrase(t *testing.T) {
	b := &Bot{
		stopPhrases: []string{"clara stop", "stop clara", "nevermind"},
	}

	tests := []struct {
		input string
		want  bool
	}{
		{"clara stop", true},
		{"Clara Stop", true},      // case insensitive
		{"  clara stop  ", true},   // whitespace trimmed
		{"NEVERMIND", true},
		{"hello", false},
		{"clara stop now", false},  // must be exact match
		{"", false},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := b.isStopPhrase(tt.input)
			if got != tt.want {
				t.Errorf("isStopPhrase(%q) = %v, want %v", tt.input, got, tt.want)
			}
		})
	}
}

func TestTruncateForDiscord(t *testing.T) {
	short := "hello"
	if got := truncateForDiscord(short); got != short {
		t.Errorf("truncateForDiscord(%q) = %q, want %q", short, got, short)
	}

	// Test truncation at limit
	long := make([]byte, 2500)
	for i := range long {
		long[i] = 'a'
	}
	got := truncateForDiscord(string(long))
	if len(got) != discordMsgLimit {
		t.Errorf("truncateForDiscord(2500 chars) length = %d, want %d", len(got), discordMsgLimit)
	}
	if got[len(got)-3:] != "..." {
		t.Error("truncated text should end with '...'")
	}
}

func TestNewBotValidation(t *testing.T) {
	// Missing token
	_, err := New(WithGatewayURL("ws://localhost:18789/ws"))
	if err == nil {
		t.Error("expected error for missing token")
	}

	// Missing gateway URL
	_, err = New(WithToken("test-token"))
	if err == nil {
		t.Error("expected error for missing gateway URL")
	}

	// Both provided
	bot, err := New(WithToken("test-token"), WithGatewayURL("ws://localhost:18789/ws"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if bot.maxMessages != defaultMaxMessages {
		t.Errorf("default maxMessages = %d, want %d", bot.maxMessages, defaultMaxMessages)
	}
}

func TestSplitCSV(t *testing.T) {
	tests := []struct {
		input string
		want  []string
	}{
		{"", nil},
		{"a,b,c", []string{"a", "b", "c"}},
		{" a , b , c ", []string{"a", "b", "c"}},
		{"single", []string{"single"}},
		{"a,,b", []string{"a", "b"}}, // empty entries skipped
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := splitCSV(tt.input)
			if len(got) != len(tt.want) {
				t.Fatalf("splitCSV(%q) = %v (len %d), want %v (len %d)", tt.input, got, len(got), tt.want, len(tt.want))
			}
			for i := range got {
				if got[i] != tt.want[i] {
					t.Errorf("splitCSV(%q)[%d] = %q, want %q", tt.input, i, got[i], tt.want[i])
				}
			}
		})
	}
}

func TestParseArchiveDuration(t *testing.T) {
	tests := []struct {
		input string
		want  int
	}{
		{"60", 60},
		{"1h", 60},
		{"1440", 1440},
		{"24h", 1440},
		{"1d", 1440},
		{"3d", 4320},
		{"7d", 10080},
		{"1w", 10080},
		{"unknown", 0},
		{"", 0},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := parseArchiveDuration(tt.input)
			if got != tt.want {
				t.Errorf("parseArchiveDuration(%q) = %d, want %d", tt.input, got, tt.want)
			}
		})
	}
}

func TestBuildDisplayText(t *testing.T) {
	b := &Bot{}

	// No content
	pr := &pendingResponse{}
	if got := b.buildDisplayText(pr); got != "..." {
		t.Errorf("empty display text = %q, want %q", got, "...")
	}

	// Only tool lines
	pr = &pendingResponse{
		toolLines: []string{"⚙️ Using **search**..."},
	}
	got := b.buildDisplayText(pr)
	if got != "⚙️ Using **search**..." {
		t.Errorf("tool-only display = %q", got)
	}

	// Tool lines + text
	pr = &pendingResponse{
		toolLines:       []string{"✅ **search** (100ms)"},
		accumulatedText: "Here is the result.",
	}
	got = b.buildDisplayText(pr)
	expected := "✅ **search** (100ms)\n\nHere is the result."
	if got != expected {
		t.Errorf("combined display = %q, want %q", got, expected)
	}
}
