package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/coder/websocket"
)

// --- NodeRegistry tests ---

func TestNodeRegistry_RegisterAndGet(t *testing.T) {
	reg := NewNodeRegistry()

	node := &ConnectedNode{
		Info: NodeInfo{
			NodeID:   "discord-1",
			Platform: "discord",
		},
		RegisteredAt: time.Now(),
		LastPing:     time.Now(),
	}

	if err := reg.Register(node); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	got := reg.Get("discord-1")
	if got == nil {
		t.Fatal("expected to find registered node")
	}
	if got.Info.Platform != "discord" {
		t.Errorf("expected platform %q, got %q", "discord", got.Info.Platform)
	}
}

func TestNodeRegistry_DuplicateRegister(t *testing.T) {
	reg := NewNodeRegistry()

	node := &ConnectedNode{
		Info: NodeInfo{NodeID: "slack-1", Platform: "slack"},
	}

	if err := reg.Register(node); err != nil {
		t.Fatalf("first register: %v", err)
	}
	if err := reg.Register(node); err == nil {
		t.Fatal("expected error on duplicate register")
	}
}

func TestNodeRegistry_Unregister(t *testing.T) {
	reg := NewNodeRegistry()

	node := &ConnectedNode{
		Info: NodeInfo{NodeID: "teams-1", Platform: "teams"},
	}
	_ = reg.Register(node)

	reg.Unregister("teams-1")

	if got := reg.Get("teams-1"); got != nil {
		t.Error("expected node to be unregistered")
	}
}

func TestNodeRegistry_UnregisterNonexistent(t *testing.T) {
	reg := NewNodeRegistry()
	// Should not panic.
	reg.Unregister("does-not-exist")
}

func TestNodeRegistry_List(t *testing.T) {
	reg := NewNodeRegistry()

	for i := 0; i < 3; i++ {
		_ = reg.Register(&ConnectedNode{
			Info: NodeInfo{
				NodeID:   fmt.Sprintf("node-%d", i),
				Platform: "test",
			},
		})
	}

	nodes := reg.List()
	if len(nodes) != 3 {
		t.Errorf("expected 3 nodes, got %d", len(nodes))
	}
}

func TestNodeRegistry_Count(t *testing.T) {
	reg := NewNodeRegistry()

	if reg.Count() != 0 {
		t.Errorf("expected 0, got %d", reg.Count())
	}

	_ = reg.Register(&ConnectedNode{
		Info: NodeInfo{NodeID: "n1", Platform: "test"},
	})
	if reg.Count() != 1 {
		t.Errorf("expected 1, got %d", reg.Count())
	}

	reg.Unregister("n1")
	if reg.Count() != 0 {
		t.Errorf("expected 0 after unregister, got %d", reg.Count())
	}
}

func TestNodeRegistry_GetNonexistent(t *testing.T) {
	reg := NewNodeRegistry()
	if got := reg.Get("nope"); got != nil {
		t.Errorf("expected nil for nonexistent node, got %+v", got)
	}
}

func TestNodeRegistry_UpdatePing(t *testing.T) {
	reg := NewNodeRegistry()
	before := time.Now().Add(-time.Hour)

	node := &ConnectedNode{
		Info:     NodeInfo{NodeID: "p1", Platform: "test"},
		LastPing: before,
	}
	_ = reg.Register(node)

	reg.UpdatePing("p1")

	got := reg.Get("p1")
	if !got.LastPing.After(before) {
		t.Error("expected LastPing to be updated")
	}
}

// --- Server tests ---

// testServer creates an httptest server backed by a gateway Server and returns
// a connected WebSocket client. The client is already past the register/registered
// handshake unless skipRegister is true.
func testServer(t *testing.T, secret string) (*Server, *httptest.Server, func(nodeID, platform string) *websocket.Conn) {
	t.Helper()

	srv := NewServer("127.0.0.1", 0, secret)
	ctx := context.Background()

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		srv.handleUpgrade(ctx, w, r)
	})
	ts := httptest.NewServer(mux)

	// Return a function that connects a client and does the register handshake.
	dial := func(nodeID, platform string) *websocket.Conn {
		t.Helper()
		wsURL := "ws" + strings.TrimPrefix(ts.URL, "http") + "/ws"
		conn, _, err := websocket.Dial(ctx, wsURL, nil)
		if err != nil {
			t.Fatalf("dial failed: %v", err)
		}

		// Send register.
		meta := map[string]any{}
		if secret != "" {
			meta["secret"] = secret
		}
		regPayload := RegisterMessage{
			Type:         MsgTypeRegister,
			NodeID:       nodeID,
			Platform:     platform,
			Capabilities: []string{"streaming"},
			Metadata:     meta,
		}
		regData, _ := MarshalMessage(MsgTypeRegister, regPayload)
		if err := conn.Write(ctx, websocket.MessageText, regData); err != nil {
			t.Fatalf("failed to send register: %v", err)
		}

		// Read registered response.
		_, data, err := conn.Read(ctx)
		if err != nil {
			t.Fatalf("failed to read registered response: %v", err)
		}
		msg, err := ParseMessage(data)
		if err != nil {
			t.Fatalf("failed to parse registered response: %v", err)
		}
		if msg.Type != MsgTypeRegistered {
			t.Fatalf("expected registered message, got %q", msg.Type)
		}

		return conn
	}

	t.Cleanup(func() {
		ts.Close()
	})

	return srv, ts, dial
}

func TestServerStartStop(t *testing.T) {
	srv := NewServer("127.0.0.1", 0, "")

	ctx, cancel := context.WithCancel(context.Background())

	errCh := make(chan error, 1)
	go func() {
		errCh <- srv.Start(ctx)
	}()

	// Give the server a moment to start.
	time.Sleep(50 * time.Millisecond)

	cancel()

	select {
	case err := <-errCh:
		if err != nil {
			t.Fatalf("unexpected error from Start: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not stop within 2 seconds")
	}
}

func TestServerRegistration(t *testing.T) {
	srv, _, dial := testServer(t, "")

	conn := dial("discord-1", "discord")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	// Verify node is registered.
	node := srv.nodes.Get("discord-1")
	if node == nil {
		t.Fatal("expected node to be registered")
	}
	if node.Info.Platform != "discord" {
		t.Errorf("expected platform %q, got %q", "discord", node.Info.Platform)
	}
}

func TestServerSecretAuth_Success(t *testing.T) {
	srv, _, dial := testServer(t, "my-secret")

	conn := dial("discord-1", "discord")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	if srv.nodes.Get("discord-1") == nil {
		t.Fatal("expected node to be registered with correct secret")
	}
}

func TestServerSecretAuth_Failure(t *testing.T) {
	srv := NewServer("127.0.0.1", 0, "my-secret")
	ctx := context.Background()

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		srv.handleUpgrade(ctx, w, r)
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	wsURL := "ws" + strings.TrimPrefix(ts.URL, "http") + "/ws"
	conn, _, err := websocket.Dial(ctx, wsURL, nil)
	if err != nil {
		t.Fatalf("dial failed: %v", err)
	}

	// Send register with wrong secret.
	regPayload := RegisterMessage{
		Type:     MsgTypeRegister,
		NodeID:   "bad-node",
		Platform: "test",
		Metadata: map[string]any{"secret": "wrong-secret"},
	}
	regData, _ := MarshalMessage(MsgTypeRegister, regPayload)
	if err := conn.Write(ctx, websocket.MessageText, regData); err != nil {
		t.Fatalf("failed to send register: %v", err)
	}

	// Should receive an error message then connection close.
	_, data, err := conn.Read(ctx)
	if err != nil {
		// Connection closed immediately is also acceptable.
		return
	}

	msg, err := ParseMessage(data)
	if err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if msg.Type != MsgTypeError {
		t.Errorf("expected error message, got %q", msg.Type)
	}
	errMsg, ok := msg.Payload.(ErrorMessage)
	if ok && errMsg.Code != "auth_failed" {
		t.Errorf("expected code %q, got %q", "auth_failed", errMsg.Code)
	}
}

func TestServerPingPong(t *testing.T) {
	_, _, dial := testServer(t, "")

	ctx := context.Background()
	conn := dial("ping-node", "test")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	// Send ping.
	pingData, _ := MarshalMessage(MsgTypePing, PingMessage{
		Type:      MsgTypePing,
		Timestamp: time.Now(),
	})
	if err := conn.Write(ctx, websocket.MessageText, pingData); err != nil {
		t.Fatalf("failed to send ping: %v", err)
	}

	// Read pong.
	readCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	_, data, err := conn.Read(readCtx)
	if err != nil {
		t.Fatalf("failed to read pong: %v", err)
	}

	// The pong comes as a raw JSON message via the send function.
	var envelope GatewayMessage
	if err := json.Unmarshal(data, &envelope); err != nil {
		t.Fatalf("failed to parse pong envelope: %v", err)
	}
	if envelope.Type != MsgTypePong {
		t.Errorf("expected pong type, got %q", envelope.Type)
	}
}

// mockProcessor records calls for testing.
type mockProcessor struct {
	mu       sync.Mutex
	calls    []*MessageRequest
	response string
}

func (m *mockProcessor) Process(ctx context.Context, req *MessageRequest, send func(msg any) error) error {
	m.mu.Lock()
	m.calls = append(m.calls, req)
	resp := m.response
	m.mu.Unlock()

	if resp == "" {
		resp = "Hello!"
	}

	// Simulate response flow: start -> end.
	_ = send(GatewayMessage{
		Type: MsgTypeResponseStart,
		Payload: ResponseStart{
			Type:      MsgTypeResponseStart,
			ID:        "resp-1",
			RequestID: req.ID,
		},
	})
	_ = send(GatewayMessage{
		Type: MsgTypeResponseEnd,
		Payload: ResponseEnd{
			Type:      MsgTypeResponseEnd,
			ID:        "resp-1",
			RequestID: req.ID,
			FullText:  resp,
		},
	})

	return nil
}

func TestServerMessageProcessing(t *testing.T) {
	srv, _, dial := testServer(t, "")

	proc := &mockProcessor{response: "Hi there!"}
	srv.SetProcessor(proc)

	ctx := context.Background()
	conn := dial("msg-node", "discord")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	// Send a message request.
	msgPayload := MessageRequest{
		Type:    MsgTypeMessage,
		ID:      "req-1",
		Content: "hello",
		User:    UserInfo{ID: "discord-123", PlatformID: "123", Name: "testuser"},
		Channel: ChannelInfo{ID: "ch-1", Type: "dm"},
	}
	msgData, _ := MarshalMessage(MsgTypeMessage, msgPayload)
	if err := conn.Write(ctx, websocket.MessageText, msgData); err != nil {
		t.Fatalf("failed to send message: %v", err)
	}

	// Read response_start and response_end.
	readCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	// We should get at least 2 messages (start + end).
	received := 0
	for received < 2 {
		_, _, err := conn.Read(readCtx)
		if err != nil {
			t.Fatalf("failed to read response %d: %v", received+1, err)
		}
		received++
	}

	// Verify processor was called.
	proc.mu.Lock()
	defer proc.mu.Unlock()
	if len(proc.calls) != 1 {
		t.Fatalf("expected 1 processor call, got %d", len(proc.calls))
	}
	if proc.calls[0].Content != "hello" {
		t.Errorf("expected content %q, got %q", "hello", proc.calls[0].Content)
	}
}

func TestServerNoProcessor(t *testing.T) {
	_, _, dial := testServer(t, "")

	ctx := context.Background()
	conn := dial("no-proc-node", "test")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	// Send message without setting a processor.
	msgData, _ := MarshalMessage(MsgTypeMessage, MessageRequest{
		Type:    MsgTypeMessage,
		ID:      "req-1",
		Content: "hello",
		User:    UserInfo{ID: "test-1"},
		Channel: ChannelInfo{ID: "ch-1", Type: "dm"},
	})
	if err := conn.Write(ctx, websocket.MessageText, msgData); err != nil {
		t.Fatalf("failed to send message: %v", err)
	}

	// Should get an error response.
	readCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	_, data, err := conn.Read(readCtx)
	if err != nil {
		t.Fatalf("failed to read error response: %v", err)
	}

	var envelope GatewayMessage
	if err := json.Unmarshal(data, &envelope); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if envelope.Type != MsgTypeError {
		t.Errorf("expected error type, got %q", envelope.Type)
	}
}

func TestServerCancel(t *testing.T) {
	srv, _, dial := testServer(t, "")

	// Create a processor that blocks until cancelled.
	blockingProc := &blockingProcessor{started: make(chan struct{})}
	srv.SetProcessor(blockingProc)

	ctx := context.Background()
	conn := dial("cancel-node", "test")
	defer conn.Close(websocket.StatusNormalClosure, "done")

	// Send a message.
	msgData, _ := MarshalMessage(MsgTypeMessage, MessageRequest{
		Type:    MsgTypeMessage,
		ID:      "req-cancel",
		Content: "long task",
		User:    UserInfo{ID: "test-1"},
		Channel: ChannelInfo{ID: "ch-1", Type: "dm"},
	})
	if err := conn.Write(ctx, websocket.MessageText, msgData); err != nil {
		t.Fatalf("failed to send message: %v", err)
	}

	// Wait for processor to start.
	select {
	case <-blockingProc.started:
	case <-time.After(2 * time.Second):
		t.Fatal("processor did not start")
	}

	// Send cancel.
	cancelData, _ := MarshalMessage(MsgTypeCancel, CancelMessage{
		Type:      MsgTypeCancel,
		RequestID: "req-cancel",
		Reason:    "user requested",
	})
	if err := conn.Write(ctx, websocket.MessageText, cancelData); err != nil {
		t.Fatalf("failed to send cancel: %v", err)
	}

	// Read the cancelled confirmation.
	readCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	_, data, err := conn.Read(readCtx)
	if err != nil {
		t.Fatalf("failed to read cancelled response: %v", err)
	}

	var envelope GatewayMessage
	if err := json.Unmarshal(data, &envelope); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if envelope.Type != MsgTypeCancelled {
		t.Errorf("expected cancelled type, got %q", envelope.Type)
	}

	// Verify the processor's context was cancelled.
	select {
	case <-blockingProc.cancelled:
	case <-time.After(2 * time.Second):
		t.Error("processor context was not cancelled")
	}
}

type blockingProcessor struct {
	started   chan struct{}
	cancelled chan struct{}
	once      sync.Once
}

func (p *blockingProcessor) Process(ctx context.Context, _ *MessageRequest, _ func(msg any) error) error {
	p.once.Do(func() {
		p.cancelled = make(chan struct{})
		close(p.started)
	})
	<-ctx.Done()
	close(p.cancelled)
	return ctx.Err()
}

func TestServerMultipleNodes(t *testing.T) {
	srv, _, dial := testServer(t, "")

	conn1 := dial("node-a", "discord")
	defer conn1.Close(websocket.StatusNormalClosure, "done")

	conn2 := dial("node-b", "slack")
	defer conn2.Close(websocket.StatusNormalClosure, "done")

	if srv.nodes.Count() != 2 {
		t.Errorf("expected 2 nodes, got %d", srv.nodes.Count())
	}

	nodes := srv.nodes.List()
	platforms := map[string]bool{}
	for _, n := range nodes {
		platforms[n.Info.Platform] = true
	}
	if !platforms["discord"] || !platforms["slack"] {
		t.Errorf("expected discord and slack platforms, got %v", platforms)
	}
}

func TestServerDisconnectCleansUp(t *testing.T) {
	srv, _, dial := testServer(t, "")

	conn := dial("temp-node", "test")

	if srv.nodes.Get("temp-node") == nil {
		t.Fatal("expected node to be registered")
	}

	// Close the connection.
	conn.Close(websocket.StatusNormalClosure, "bye")

	// Give the server a moment to process the disconnect.
	time.Sleep(100 * time.Millisecond)

	if srv.nodes.Get("temp-node") != nil {
		t.Error("expected node to be unregistered after disconnect")
	}
}
