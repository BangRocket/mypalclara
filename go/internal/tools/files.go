package tools

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// DefaultFilesDir is the base directory for user file storage.
const DefaultFilesDir = "./clara_files"

// FileTools provides file operation tools for user local storage.
type FileTools struct {
	baseDir string
}

// NewFileTools creates file tools with the given base directory.
// If baseDir is empty, DefaultFilesDir is used.
func NewFileTools(baseDir string) *FileTools {
	if baseDir == "" {
		baseDir = DefaultFilesDir
	}
	return &FileTools{baseDir: baseDir}
}

// Register adds all file tools to the registry.
func (ft *FileTools) Register(reg *Registry) {
	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "save_to_local",
			Description: "Save content to a file in the user's local storage.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"filename": map[string]any{
						"type":        "string",
						"description": "Name of the file to save (no path separators).",
					},
					"content": map[string]any{
						"type":        "string",
						"description": "Content to write to the file.",
					},
				},
				"required": []string{"filename", "content"},
			},
		},
		Handler: ft.handleSave,
	})

	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "read_local_file",
			Description: "Read a file from the user's local storage.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"filename": map[string]any{
						"type":        "string",
						"description": "Name of the file to read.",
					},
				},
				"required": []string{"filename"},
			},
		},
		Handler: ft.handleRead,
	})

	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "list_local_files",
			Description: "List files in the user's local storage.",
			Parameters: map[string]any{
				"type":       "object",
				"properties": map[string]any{},
			},
		},
		Handler: ft.handleList,
	})

	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "delete_local_file",
			Description: "Delete a file from the user's local storage.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"filename": map[string]any{
						"type":        "string",
						"description": "Name of the file to delete.",
					},
				},
				"required": []string{"filename"},
			},
		},
		Handler: ft.handleDelete,
	})
}

// userDir returns the storage directory for a given user, creating it if needed.
func (ft *FileTools) userDir(userID string) (string, error) {
	// Sanitize user ID to prevent path traversal.
	safe := sanitizeFilename(userID)
	if safe == "" {
		return "", fmt.Errorf("invalid user ID")
	}
	dir := filepath.Join(ft.baseDir, safe)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("failed to create user directory: %w", err)
	}
	return dir, nil
}

// sanitizeFilename removes path separators and dangerous patterns.
func sanitizeFilename(name string) string {
	name = filepath.Base(name)
	name = strings.ReplaceAll(name, "..", "")
	name = strings.TrimSpace(name)
	if name == "." || name == "" {
		return ""
	}
	return name
}

func (ft *FileTools) handleSave(_ context.Context, args map[string]any, userID string) (string, error) {
	filename, _ := args["filename"].(string)
	content, _ := args["content"].(string)
	if filename == "" {
		return "", fmt.Errorf("filename is required")
	}

	safe := sanitizeFilename(filename)
	if safe == "" {
		return "", fmt.Errorf("invalid filename: %q", filename)
	}

	dir, err := ft.userDir(userID)
	if err != nil {
		return "", err
	}

	path := filepath.Join(dir, safe)
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	return fmt.Sprintf("Saved %q (%d bytes)", safe, len(content)), nil
}

func (ft *FileTools) handleRead(_ context.Context, args map[string]any, userID string) (string, error) {
	filename, _ := args["filename"].(string)
	if filename == "" {
		return "", fmt.Errorf("filename is required")
	}

	safe := sanitizeFilename(filename)
	if safe == "" {
		return "", fmt.Errorf("invalid filename: %q", filename)
	}

	dir, err := ft.userDir(userID)
	if err != nil {
		return "", err
	}

	data, err := os.ReadFile(filepath.Join(dir, safe))
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("file %q not found", safe)
		}
		return "", fmt.Errorf("failed to read file: %w", err)
	}

	return string(data), nil
}

func (ft *FileTools) handleList(_ context.Context, _ map[string]any, userID string) (string, error) {
	dir, err := ft.userDir(userID)
	if err != nil {
		return "", err
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return "No files found.", nil
		}
		return "", fmt.Errorf("failed to list files: %w", err)
	}

	if len(entries) == 0 {
		return "No files found.", nil
	}

	var sb strings.Builder
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		sb.WriteString(fmt.Sprintf("- %s (%d bytes)\n", e.Name(), info.Size()))
	}

	result := sb.String()
	if result == "" {
		return "No files found.", nil
	}
	return result, nil
}

func (ft *FileTools) handleDelete(_ context.Context, args map[string]any, userID string) (string, error) {
	filename, _ := args["filename"].(string)
	if filename == "" {
		return "", fmt.Errorf("filename is required")
	}

	safe := sanitizeFilename(filename)
	if safe == "" {
		return "", fmt.Errorf("invalid filename: %q", filename)
	}

	dir, err := ft.userDir(userID)
	if err != nil {
		return "", err
	}

	path := filepath.Join(dir, safe)
	if err := os.Remove(path); err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("file %q not found", safe)
		}
		return "", fmt.Errorf("failed to delete file: %w", err)
	}

	return fmt.Sprintf("Deleted %q", safe), nil
}
