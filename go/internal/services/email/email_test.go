package email

import (
	"testing"
)

func TestMonitorDisabledByDefault(t *testing.T) {
	// With no env vars set, the monitor should be disabled.
	m := NewMonitor()

	if m.Enabled() {
		t.Fatal("expected monitor to be disabled by default")
	}

	// CheckInbox should return an error when disabled.
	_, err := m.CheckInbox(nil)
	if err == nil {
		t.Fatal("expected error when checking inbox while disabled")
	}
}
