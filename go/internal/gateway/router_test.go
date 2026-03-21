package gateway

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// routerTestProcessor records calls and allows controlling processing time.
type routerTestProcessor struct {
	mu     sync.Mutex
	calls  []*MessageRequest
	delay  time.Duration
	onCall func(req *MessageRequest) // optional hook called during Process
}

func (p *routerTestProcessor) Process(ctx context.Context, req *MessageRequest, send func(msg any) error) error {
	p.mu.Lock()
	p.calls = append(p.calls, req)
	delay := p.delay
	hook := p.onCall
	p.mu.Unlock()

	if hook != nil {
		hook(req)
	}
	if delay > 0 {
		select {
		case <-time.After(delay):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	return nil
}

func (p *routerTestProcessor) callCount() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.calls)
}

func TestRouterDedup(t *testing.T) {
	proc := &routerTestProcessor{}
	r := NewRouter(proc)
	r.debounce = 10 * time.Millisecond // speed up test

	req := &MessageRequest{
		ID:      "msg-123",
		Channel: ChannelInfo{ID: "chan-1"},
		Content: "hello",
	}

	// Submit same message ID twice rapidly.
	if err := r.Submit(req); err != nil {
		t.Fatalf("first submit: %v", err)
	}
	if err := r.Submit(req); err != nil {
		t.Fatalf("second submit: %v", err)
	}

	// Wait for processing to complete.
	time.Sleep(200 * time.Millisecond)

	count := proc.callCount()
	if count != 1 {
		t.Errorf("expected 1 call (dedup), got %d", count)
	}
}

func TestRouterSerialProcessing(t *testing.T) {
	// Track concurrent executions per channel.
	var maxConcurrent int32
	var current int32

	proc := &routerTestProcessor{
		delay: 50 * time.Millisecond,
		onCall: func(req *MessageRequest) {
			c := atomic.AddInt32(&current, 1)
			for {
				old := atomic.LoadInt32(&maxConcurrent)
				if c <= old || atomic.CompareAndSwapInt32(&maxConcurrent, old, c) {
					break
				}
			}
			// Hold for a bit so overlap is detectable.
			time.Sleep(20 * time.Millisecond)
			atomic.AddInt32(&current, -1)
		},
	}

	r := NewRouter(proc)
	r.debounce = 5 * time.Millisecond // speed up test

	// Submit 3 messages to the same channel.
	for i := 0; i < 3; i++ {
		req := &MessageRequest{
			ID:      fmt.Sprintf("msg-%d", i),
			Channel: ChannelInfo{ID: "chan-serial"},
			Content: fmt.Sprintf("message %d", i),
		}
		if err := r.Submit(req); err != nil {
			t.Fatalf("submit %d: %v", i, err)
		}
	}

	// Wait for all to complete.
	time.Sleep(500 * time.Millisecond)

	if mc := atomic.LoadInt32(&maxConcurrent); mc > 1 {
		t.Errorf("expected max 1 concurrent per channel, got %d", mc)
	}

	count := proc.callCount()
	if count != 3 {
		t.Errorf("expected 3 calls, got %d", count)
	}
}

func TestRouterDifferentChannelsParallel(t *testing.T) {
	// Different channels should process in parallel.
	var started int32

	gate := make(chan struct{}) // holds all processing until we release

	proc := &routerTestProcessor{
		onCall: func(req *MessageRequest) {
			atomic.AddInt32(&started, 1)
			<-gate
		},
	}

	r := NewRouter(proc)
	r.debounce = 5 * time.Millisecond

	// Submit to 3 different channels.
	for i := 0; i < 3; i++ {
		req := &MessageRequest{
			ID:      fmt.Sprintf("msg-%d", i),
			Channel: ChannelInfo{ID: fmt.Sprintf("chan-%d", i)},
			Content: "hello",
		}
		if err := r.Submit(req); err != nil {
			t.Fatalf("submit %d: %v", i, err)
		}
	}

	// Wait for debounce + goroutine startup.
	time.Sleep(100 * time.Millisecond)

	s := atomic.LoadInt32(&started)
	if s < 2 {
		t.Errorf("expected at least 2 channels processing in parallel, got %d", s)
	}

	close(gate) // release all
	time.Sleep(100 * time.Millisecond)
}
