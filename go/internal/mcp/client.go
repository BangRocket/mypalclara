package mcp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"sync/atomic"
)

// jsonRPCRequest is a JSON-RPC 2.0 request.
type jsonRPCRequest struct {
	JSONRPC string `json:"jsonrpc"`
	ID      int64  `json:"id"`
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

// jsonRPCResponse is a JSON-RPC 2.0 response.
type jsonRPCResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      int64           `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *jsonRPCError   `json:"error,omitempty"`
}

type jsonRPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// initializeResult holds the response from MCP initialize.
type initializeResult struct {
	ProtocolVersion string `json:"protocolVersion"`
	ServerInfo      struct {
		Name    string `json:"name"`
		Version string `json:"version"`
	} `json:"serverInfo"`
}

// toolsListResult holds the response from tools/list.
type toolsListResult struct {
	Tools []Tool `json:"tools"`
}

// toolCallResult holds the response from tools/call.
type toolCallResult struct {
	Content []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	IsError bool `json:"isError,omitempty"`
}

// Client manages connections to a single MCP server.
type Client struct {
	name      string
	tools     []Tool
	connected bool
}

// LocalClient connects to a local MCP server via stdio.
type LocalClient struct {
	Client
	config  LocalServerConfig
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	stdout  io.ReadCloser
	scanner *bufio.Scanner
	nextID  atomic.Int64
	mu      sync.Mutex
}

// NewLocalClient creates a new LocalClient from config.
func NewLocalClient(config LocalServerConfig) *LocalClient {
	return &LocalClient{
		Client: Client{
			name: config.Name,
		},
		config: config,
	}
}

// Connect starts the subprocess and initializes the MCP protocol.
func (c *LocalClient) Connect(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	cmd := exec.CommandContext(ctx, c.config.Command, c.config.Args...)
	if c.config.CWD != "" {
		cmd.Dir = c.config.CWD
	}
	if len(c.config.Env) > 0 {
		for k, v := range c.config.Env {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("mcp: stdin pipe: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("mcp: stdout pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("mcp: start %q: %w", c.config.Command, err)
	}

	c.cmd = cmd
	c.stdin = stdin
	c.stdout = stdout
	c.scanner = bufio.NewScanner(stdout)
	c.scanner.Buffer(make([]byte, 0, 1024*1024), 1024*1024) // 1MB buffer

	// Initialize MCP protocol.
	var initResult initializeResult
	err = c.call(ctx, "initialize", map[string]any{
		"protocolVersion": "2024-11-05",
		"capabilities":    map[string]any{},
		"clientInfo": map[string]any{
			"name":    "mypalclara-go",
			"version": "1.0.0",
		},
	}, &initResult)
	if err != nil {
		_ = c.disconnectLocked()
		return fmt.Errorf("mcp: initialize: %w", err)
	}

	// Send initialized notification (no id, no response expected).
	if err := c.notify("notifications/initialized", nil); err != nil {
		_ = c.disconnectLocked()
		return fmt.Errorf("mcp: initialized notification: %w", err)
	}

	// Discover tools.
	var toolsResult toolsListResult
	err = c.call(ctx, "tools/list", map[string]any{}, &toolsResult)
	if err != nil {
		_ = c.disconnectLocked()
		return fmt.Errorf("mcp: tools/list: %w", err)
	}

	c.tools = toolsResult.Tools
	c.connected = true
	return nil
}

// call sends a JSON-RPC request and reads the response.
func (c *LocalClient) call(_ context.Context, method string, params any, result any) error {
	id := c.nextID.Add(1)
	req := jsonRPCRequest{
		JSONRPC: "2.0",
		ID:      id,
		Method:  method,
		Params:  params,
	}

	data, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}
	data = append(data, '\n')

	if _, err := c.stdin.Write(data); err != nil {
		return fmt.Errorf("write request: %w", err)
	}

	// Read lines until we get a JSON-RPC response with our ID.
	// Skip notifications (lines without an id field matching ours).
	for {
		if !c.scanner.Scan() {
			if err := c.scanner.Err(); err != nil {
				return fmt.Errorf("read response: %w", err)
			}
			return fmt.Errorf("read response: unexpected EOF")
		}

		line := c.scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var resp jsonRPCResponse
		if err := json.Unmarshal(line, &resp); err != nil {
			// Skip non-JSON lines (e.g., server logs to stdout).
			continue
		}

		if resp.ID != id {
			// Not our response; could be a notification or response to another request.
			continue
		}

		if resp.Error != nil {
			return fmt.Errorf("rpc error %d: %s", resp.Error.Code, resp.Error.Message)
		}

		if result != nil {
			return json.Unmarshal(resp.Result, result)
		}
		return nil
	}
}

// notify sends a JSON-RPC notification (no id, no response).
func (c *LocalClient) notify(method string, params any) error {
	type notification struct {
		JSONRPC string `json:"jsonrpc"`
		Method  string `json:"method"`
		Params  any    `json:"params,omitempty"`
	}
	data, err := json.Marshal(notification{
		JSONRPC: "2.0",
		Method:  method,
		Params:  params,
	})
	if err != nil {
		return fmt.Errorf("marshal notification: %w", err)
	}
	data = append(data, '\n')
	_, err = c.stdin.Write(data)
	return err
}

// CallTool executes a tool and returns the result.
func (c *LocalClient) CallTool(ctx context.Context, toolName string, args map[string]any) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.connected {
		return "", fmt.Errorf("mcp: client %q not connected", c.name)
	}

	var result toolCallResult
	err := c.call(ctx, "tools/call", map[string]any{
		"name":      toolName,
		"arguments": args,
	}, &result)
	if err != nil {
		return "", fmt.Errorf("mcp: call tool %q: %w", toolName, err)
	}

	if result.IsError {
		var texts []string
		for _, c := range result.Content {
			if c.Type == "text" {
				texts = append(texts, c.Text)
			}
		}
		if len(texts) > 0 {
			return "", fmt.Errorf("mcp: tool error: %s", texts[0])
		}
		return "", fmt.Errorf("mcp: tool %q returned error", toolName)
	}

	// Concatenate text content.
	var out string
	for _, c := range result.Content {
		if c.Type == "text" {
			if out != "" {
				out += "\n"
			}
			out += c.Text
		}
	}
	return out, nil
}

// ListTools returns discovered tools.
func (c *LocalClient) ListTools() []Tool {
	return c.tools
}

// Disconnect stops the subprocess.
func (c *LocalClient) Disconnect() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.disconnectLocked()
}

func (c *LocalClient) disconnectLocked() error {
	c.connected = false
	if c.stdin != nil {
		_ = c.stdin.Close()
	}
	if c.cmd != nil && c.cmd.Process != nil {
		_ = c.cmd.Process.Kill()
		_ = c.cmd.Wait()
	}
	return nil
}

// RemoteClient connects to a remote MCP server via HTTP.
type RemoteClient struct {
	Client
	config RemoteServerConfig
}

// NewRemoteClient creates a new RemoteClient from config.
func NewRemoteClient(config RemoteServerConfig) *RemoteClient {
	return &RemoteClient{
		Client: Client{
			name: config.Name,
		},
		config: config,
	}
}

// Connect establishes connection to the remote MCP server.
func (c *RemoteClient) Connect(ctx context.Context) error {
	// TODO: Implement HTTP/SSE transport for remote MCP servers.
	return fmt.Errorf("mcp: remote client not yet implemented")
}

// CallTool executes a tool on the remote server.
func (c *RemoteClient) CallTool(ctx context.Context, toolName string, args map[string]any) (string, error) {
	return "", fmt.Errorf("mcp: remote client not yet implemented")
}

// ListTools returns discovered tools.
func (c *RemoteClient) ListTools() []Tool {
	return c.tools
}

// Disconnect closes the connection.
func (c *RemoteClient) Disconnect() error {
	c.connected = false
	return nil
}
