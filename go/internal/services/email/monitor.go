// Package email provides IMAP email monitoring for Clara.
package email

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"time"
)

// Email represents a single email message.
type Email struct {
	From    string
	Subject string
	Body    string
	Date    time.Time
}

// Monitor connects to an IMAP server and checks for new emails.
type Monitor struct {
	host     string
	port     int
	username string
	password string
	enabled  bool
	cancel   context.CancelFunc
}

// NewMonitor creates a Monitor from EMAIL_* environment variables.
//
// Required env vars for enabled operation:
//   - EMAIL_MONITORING_ENABLED=true
//   - EMAIL_IMAP_HOST
//   - EMAIL_IMAP_PORT (default: 993)
//   - EMAIL_USERNAME
//   - EMAIL_PASSWORD
func NewMonitor() *Monitor {
	enabled, _ := strconv.ParseBool(os.Getenv("EMAIL_MONITORING_ENABLED"))
	port := 993
	if p := os.Getenv("EMAIL_IMAP_PORT"); p != "" {
		if v, err := strconv.Atoi(p); err == nil {
			port = v
		}
	}

	return &Monitor{
		host:     os.Getenv("EMAIL_IMAP_HOST"),
		port:     port,
		username: os.Getenv("EMAIL_USERNAME"),
		password: os.Getenv("EMAIL_PASSWORD"),
		enabled:  enabled,
	}
}

// Enabled reports whether email monitoring is configured and enabled.
func (m *Monitor) Enabled() bool {
	return m.enabled
}

// Start begins periodic inbox checking. It blocks until the context is
// cancelled or Stop is called. Returns immediately if not enabled.
func (m *Monitor) Start(ctx context.Context) error {
	if !m.enabled {
		return nil
	}

	if m.host == "" || m.username == "" || m.password == "" {
		return fmt.Errorf("email monitoring enabled but EMAIL_IMAP_HOST, EMAIL_USERNAME, or EMAIL_PASSWORD not set")
	}

	ctx, cancel := context.WithCancel(ctx)
	m.cancel = cancel
	defer cancel()

	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			// TODO: call CheckInbox and dispatch to Clara for auto-response.
			_, _ = m.CheckInbox(ctx)
		}
	}
}

// Stop signals the monitor to stop.
func (m *Monitor) Stop() error {
	if m.cancel != nil {
		m.cancel()
	}
	return nil
}

// CheckInbox connects to the IMAP server and fetches recent emails.
// This is a stub implementation -- full IMAP logic using go-imap comes later.
func (m *Monitor) CheckInbox(_ context.Context) ([]Email, error) {
	if !m.enabled {
		return nil, fmt.Errorf("email monitoring is disabled")
	}

	// Stub: return empty list. Real implementation will use go-imap to:
	// 1. Connect via TLS to m.host:m.port
	// 2. Login with m.username/m.password
	// 3. Select INBOX
	// 4. Search for UNSEEN messages
	// 5. Fetch and parse message bodies
	return []Email{}, nil
}
