// Package backup provides automated PostgreSQL backup to S3-compatible storage.
package backup

import (
	"context"
	"fmt"
	"os"
	"time"
)

// BackupInfo describes a stored backup.
type BackupInfo struct {
	Key       string
	Size      int64
	Timestamp time.Time
}

// Service manages database backups to S3-compatible storage (e.g., Wasabi).
type Service struct {
	bucket      string
	endpoint    string
	accessKey   string
	secretKey   string
	databaseURL string
	enabled     bool
}

// NewService creates a backup Service from environment variables.
//
// Required env vars for enabled operation:
//   - S3_BUCKET
//   - S3_ENDPOINT_URL
//   - S3_ACCESS_KEY
//   - S3_SECRET_KEY
//   - DATABASE_URL
func NewService() *Service {
	bucket := os.Getenv("S3_BUCKET")
	endpoint := os.Getenv("S3_ENDPOINT_URL")
	accessKey := os.Getenv("S3_ACCESS_KEY")
	secretKey := os.Getenv("S3_SECRET_KEY")
	databaseURL := os.Getenv("DATABASE_URL")

	enabled := bucket != "" && endpoint != "" && accessKey != "" && secretKey != "" && databaseURL != ""

	return &Service{
		bucket:      bucket,
		endpoint:    endpoint,
		accessKey:   accessKey,
		secretKey:   secretKey,
		databaseURL: databaseURL,
		enabled:     enabled,
	}
}

// Enabled reports whether the backup service is configured.
func (s *Service) Enabled() bool {
	return s.enabled
}

// Backup runs pg_dump and uploads the result to S3.
// This is a stub implementation -- full logic using aws-sdk-go-v2 comes later.
func (s *Service) Backup(_ context.Context) error {
	if !s.enabled {
		return fmt.Errorf("backup service is not configured: set S3_BUCKET, S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, and DATABASE_URL")
	}

	// Stub implementation. Real version will:
	// 1. Run pg_dump on s.databaseURL to a temp file
	// 2. Upload the dump file to s.bucket at s.endpoint using S3 API
	// 3. Clean up the temp file
	return nil
}

// ListBackups returns metadata for all backups in the S3 bucket.
// This is a stub implementation.
func (s *Service) ListBackups(_ context.Context) ([]BackupInfo, error) {
	if !s.enabled {
		return nil, fmt.Errorf("backup service is not configured")
	}

	// Stub: return empty list. Real implementation will use aws-sdk-go-v2 to
	// list objects in s.bucket with the backup prefix.
	return []BackupInfo{}, nil
}
