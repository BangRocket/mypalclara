package sandbox

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"time"
)

// ExecutionResult from sandbox command.
type ExecutionResult struct {
	Success bool   `json:"success"`
	Output  string `json:"output"`
	Error   string `json:"error,omitempty"`
}

// Manager handles code execution in Docker containers.
type Manager struct {
	image   string
	timeout int  // seconds
	enabled bool // whether Docker is available
}

// NewManager creates a sandbox Manager, detecting Docker availability.
func NewManager() *Manager {
	image := os.Getenv("DOCKER_SANDBOX_IMAGE")
	if image == "" {
		image = "python:3.12-slim"
	}

	timeout := 900
	if t := os.Getenv("DOCKER_SANDBOX_TIMEOUT"); t != "" {
		if v, err := strconv.Atoi(t); err == nil && v > 0 {
			timeout = v
		}
	}

	enabled := isDockerAvailable()

	return &Manager{
		image:   image,
		timeout: timeout,
		enabled: enabled,
	}
}

// IsEnabled reports whether Docker is available.
func (m *Manager) IsEnabled() bool {
	return m.enabled
}

// ExecutePython runs Python code in a Docker container.
func (m *Manager) ExecutePython(ctx context.Context, userID, code string) (*ExecutionResult, error) {
	if !m.enabled {
		return nil, fmt.Errorf("docker is not available")
	}

	return m.runContainer(ctx, userID, []string{"python3", "-c", code})
}

// RunShell runs a shell command in a Docker container.
func (m *Manager) RunShell(ctx context.Context, userID, command string) (*ExecutionResult, error) {
	if !m.enabled {
		return nil, fmt.Errorf("docker is not available")
	}

	return m.runContainer(ctx, userID, []string{"sh", "-c", command})
}

// HandleToolCall routes sandbox tool calls.
func (m *Manager) HandleToolCall(ctx context.Context, userID, toolName string, args map[string]any) (*ExecutionResult, error) {
	switch toolName {
	case "execute_python":
		code, _ := args["code"].(string)
		if code == "" {
			return nil, fmt.Errorf("code is required for execute_python")
		}
		return m.ExecutePython(ctx, userID, code)

	case "run_shell":
		command, _ := args["command"].(string)
		if command == "" {
			return nil, fmt.Errorf("command is required for run_shell")
		}
		return m.RunShell(ctx, userID, command)

	default:
		return nil, fmt.Errorf("unknown sandbox tool: %q", toolName)
	}
}

// runContainer executes a command in a Docker container.
func (m *Manager) runContainer(ctx context.Context, _ string, command []string) (*ExecutionResult, error) {
	timeout := time.Duration(m.timeout) * time.Second
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	args := []string{
		"run", "--rm",
		"--network", "none",
		"--memory", "512m",
		"--cpus", "1",
		"--pids-limit", "100",
		"--read-only",
		"--tmpfs", "/tmp:size=100m",
		m.image,
	}
	args = append(args, command...)

	cmd := exec.CommandContext(ctx, "docker", args...)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	result := &ExecutionResult{
		Output: stdout.String(),
	}

	if err != nil {
		result.Success = false
		result.Error = stderr.String()
		if result.Error == "" {
			result.Error = err.Error()
		}
		// Context deadline = timeout, not a hard error.
		if ctx.Err() == context.DeadlineExceeded {
			result.Error = fmt.Sprintf("execution timed out after %d seconds", m.timeout)
		}
	} else {
		result.Success = true
		// Include stderr in output if present (warnings, etc.).
		if stderr.Len() > 0 {
			result.Output += "\n[stderr]\n" + stderr.String()
		}
	}

	return result, nil
}

// isDockerAvailable checks whether Docker is accessible.
func isDockerAvailable() bool {
	cmd := exec.Command("docker", "info")
	cmd.Stdout = nil
	cmd.Stderr = nil
	return cmd.Run() == nil
}
