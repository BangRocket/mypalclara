package tools

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestRegistryRegisterAndGet(t *testing.T) {
	reg := NewRegistry()
	if len(reg.GetSchemas()) != 0 {
		t.Fatal("new registry should have no schemas")
	}

	// Register file tools and skill tools.
	ft := NewFileTools(t.TempDir())
	ft.Register(reg)

	st := NewSkillTools(t.TempDir())
	st.Register(reg)

	schemas := reg.GetSchemas()
	// 4 file tools + 2 skill tools = 6
	if len(schemas) != 6 {
		t.Fatalf("expected 6 schemas, got %d", len(schemas))
	}

	// Check that all expected tool names are present.
	names := make(map[string]bool)
	for _, s := range schemas {
		names[s.Name] = true
	}

	expected := []string{
		"save_to_local", "read_local_file", "list_local_files", "delete_local_file",
		"load_skill", "list_skills",
	}
	for _, name := range expected {
		if !names[name] {
			t.Errorf("missing expected tool %q", name)
		}
	}
}

func TestFileToolSaveAndRead(t *testing.T) {
	dir := t.TempDir()
	ft := NewFileTools(dir)
	ctx := context.Background()
	userID := "test-user"

	// Save a file.
	result, err := ft.handleSave(ctx, map[string]any{
		"filename": "hello.txt",
		"content":  "Hello, Clara!",
	}, userID)
	if err != nil {
		t.Fatalf("save failed: %v", err)
	}
	if result == "" {
		t.Fatal("save returned empty result")
	}

	// Verify file exists on disk.
	data, err := os.ReadFile(filepath.Join(dir, "test-user", "hello.txt"))
	if err != nil {
		t.Fatalf("file not found on disk: %v", err)
	}
	if string(data) != "Hello, Clara!" {
		t.Fatalf("file content mismatch: got %q", string(data))
	}

	// Read it back via handler.
	content, err := ft.handleRead(ctx, map[string]any{
		"filename": "hello.txt",
	}, userID)
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	if content != "Hello, Clara!" {
		t.Fatalf("read content mismatch: got %q", content)
	}

	// Read non-existent file.
	_, err = ft.handleRead(ctx, map[string]any{
		"filename": "nope.txt",
	}, userID)
	if err == nil {
		t.Fatal("expected error reading non-existent file")
	}

	// Delete the file.
	result, err = ft.handleDelete(ctx, map[string]any{
		"filename": "hello.txt",
	}, userID)
	if err != nil {
		t.Fatalf("delete failed: %v", err)
	}
	if result == "" {
		t.Fatal("delete returned empty result")
	}

	// Verify it's gone.
	_, err = ft.handleRead(ctx, map[string]any{
		"filename": "hello.txt",
	}, userID)
	if err == nil {
		t.Fatal("expected error reading deleted file")
	}
}

func TestFileToolList(t *testing.T) {
	dir := t.TempDir()
	ft := NewFileTools(dir)
	ctx := context.Background()
	userID := "test-user"

	// List empty directory.
	result, err := ft.handleList(ctx, nil, userID)
	if err != nil {
		t.Fatalf("list failed: %v", err)
	}
	if result != "No files found." {
		t.Fatalf("expected 'No files found.', got %q", result)
	}

	// Create some files.
	for _, name := range []string{"a.txt", "b.txt", "c.txt"} {
		_, err := ft.handleSave(ctx, map[string]any{
			"filename": name,
			"content":  "content of " + name,
		}, userID)
		if err != nil {
			t.Fatalf("save %s failed: %v", name, err)
		}
	}

	result, err = ft.handleList(ctx, nil, userID)
	if err != nil {
		t.Fatalf("list failed: %v", err)
	}

	// Check all files are listed.
	for _, name := range []string{"a.txt", "b.txt", "c.txt"} {
		if !contains(result, name) {
			t.Errorf("list result missing %q: %s", name, result)
		}
	}
}

func TestFileToolPathTraversal(t *testing.T) {
	dir := t.TempDir()
	ft := NewFileTools(dir)
	ctx := context.Background()

	// Attempt path traversal in filename.
	_, err := ft.handleSave(ctx, map[string]any{
		"filename": "../../../etc/passwd",
		"content":  "pwned",
	}, "test-user")
	if err != nil {
		t.Fatalf("save should succeed with sanitized name, got: %v", err)
	}

	// The file should be saved as "passwd" (filepath.Base strips the path).
	data, err := os.ReadFile(filepath.Join(dir, "test-user", "passwd"))
	if err != nil {
		t.Fatalf("sanitized file not found: %v", err)
	}
	if string(data) != "pwned" {
		t.Fatalf("unexpected content: %q", string(data))
	}

	// Verify no file was written outside the base dir.
	if _, err := os.Stat("/tmp/etc/passwd"); err == nil {
		t.Fatal("path traversal succeeded!")
	}
}

func TestSkillToolsLoadAndList(t *testing.T) {
	dir := t.TempDir()

	// Create a skill directory with an instruction file.
	skillDir := filepath.Join(dir, "code_review")
	if err := os.MkdirAll(skillDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(skillDir, "instructions.md"), []byte("# Code Review\nReview the code."), 0o644); err != nil {
		t.Fatal(err)
	}

	// Create a directory without instruction files (should not appear in list).
	emptyDir := filepath.Join(dir, "empty_skill")
	if err := os.MkdirAll(emptyDir, 0o755); err != nil {
		t.Fatal(err)
	}

	st := NewSkillTools(dir)
	ctx := context.Background()

	// List skills.
	result, err := st.handleList(ctx, nil, "")
	if err != nil {
		t.Fatalf("list failed: %v", err)
	}
	if !contains(result, "code_review") {
		t.Errorf("list should contain code_review: %s", result)
	}
	if contains(result, "empty_skill") {
		t.Error("list should not contain empty_skill")
	}

	// Load skill.
	content, err := st.handleLoad(ctx, map[string]any{"skill_name": "code_review"}, "")
	if err != nil {
		t.Fatalf("load failed: %v", err)
	}
	if content != "# Code Review\nReview the code." {
		t.Fatalf("unexpected content: %q", content)
	}

	// Load non-existent skill.
	_, err = st.handleLoad(ctx, map[string]any{"skill_name": "nope"}, "")
	if err == nil {
		t.Fatal("expected error loading non-existent skill")
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsSubstr(s, substr))
}

func containsSubstr(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
