// Package gateway — router.go implements per-channel message queuing with
// debounce and deduplication.
//
// Ported from the Python gateway's message routing logic.
package gateway

import (
	"context"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

const (
	// DefaultDebounce is how long to wait for rapid-fire messages before
	// processing. Consolidates bursts from the same channel.
	DefaultDebounce = 2 * time.Second

	// DefaultDedupTTL is how long to remember a message ID for dedup.
	DefaultDedupTTL = 30 * time.Second
)

// Router manages per-channel message queuing with debounce and dedup.
// One request is active per channel at a time (serialized); different channels
// process in parallel.
type Router struct {
	channels  map[string]*channelQueue
	processor Processor
	debounce  time.Duration
	dedupTTL  time.Duration
	mu        sync.Mutex
}

// channelQueue holds the pending messages and dedup state for a single channel.
type channelQueue struct {
	active    bool
	pending   []*MessageRequest
	lastMsgID map[string]time.Time // message ID → first-seen time
	mu        sync.Mutex
}

// NewRouter creates a Router that dispatches requests to the given processor.
func NewRouter(processor Processor) *Router {
	return &Router{
		channels:  make(map[string]*channelQueue),
		processor: processor,
		debounce:  DefaultDebounce,
		dedupTTL:  DefaultDedupTTL,
	}
}

// Submit adds a message request to the channel queue.
// Returns immediately — processing happens asynchronously.
func (r *Router) Submit(req *MessageRequest) error {
	channelID := req.Channel.ID

	r.mu.Lock()
	cq, exists := r.channels[channelID]
	if !exists {
		cq = &channelQueue{
			lastMsgID: make(map[string]time.Time),
		}
		r.channels[channelID] = cq
	}
	r.mu.Unlock()

	cq.mu.Lock()
	defer cq.mu.Unlock()

	// Dedup: skip if we've seen this message ID recently.
	if req.ID != "" {
		if seen, ok := cq.lastMsgID[req.ID]; ok {
			if time.Since(seen) < r.dedupTTL {
				log.Debug().
					Str("channel", channelID).
					Str("msg_id", req.ID).
					Msg("router: dedup — skipping duplicate message")
				return nil
			}
		}
		cq.lastMsgID[req.ID] = time.Now()
		r.cleanupDedup(cq)
	}

	cq.pending = append(cq.pending, req)

	// If no goroutine is actively processing this channel, start one.
	if !cq.active {
		cq.active = true
		go r.processChannel(context.Background(), channelID)
	}

	return nil
}

// processChannel handles messages for a single channel serially.
// It processes one message at a time, with a debounce delay between them.
func (r *Router) processChannel(ctx context.Context, channelID string) {
	for {
		// Debounce: wait before picking up the next message so rapid-fire
		// messages can consolidate in the queue.
		select {
		case <-time.After(r.debounce):
		case <-ctx.Done():
			return
		}

		r.mu.Lock()
		cq, exists := r.channels[channelID]
		r.mu.Unlock()
		if !exists {
			return
		}

		cq.mu.Lock()
		if len(cq.pending) == 0 {
			cq.active = false
			cq.mu.Unlock()
			return
		}

		// Take the first pending message.
		req := cq.pending[0]
		cq.pending = cq.pending[1:]
		cq.mu.Unlock()

		// Process with a no-op send function (the real send comes from the
		// server layer; the router just serializes execution).
		logger := log.With().
			Str("channel", channelID).
			Str("msg_id", req.ID).
			Logger()

		logger.Debug().Msg("router: processing message")

		err := r.processor.Process(ctx, req, func(msg any) error { return nil })
		if err != nil {
			logger.Error().Err(err).Msg("router: processing failed")
		}
	}
}

// cleanupDedup removes expired entries from the dedup map.
// Must be called with cq.mu held.
func (r *Router) cleanupDedup(cq *channelQueue) {
	now := time.Now()
	for id, seen := range cq.lastMsgID {
		if now.Sub(seen) > r.dedupTTL {
			delete(cq.lastMsgID, id)
		}
	}
}
