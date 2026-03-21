package backup

import (
	"context"
	"testing"
)

func TestServiceDisabledByDefault(t *testing.T) {
	// With no env vars set, the service should be disabled.
	s := NewService()

	if s.Enabled() {
		t.Fatal("expected backup service to be disabled by default")
	}

	// Backup should return an error when not configured.
	err := s.Backup(context.Background())
	if err == nil {
		t.Fatal("expected error when backing up without configuration")
	}

	// ListBackups should also return an error.
	_, err = s.ListBackups(context.Background())
	if err == nil {
		t.Fatal("expected error when listing backups without configuration")
	}
}
