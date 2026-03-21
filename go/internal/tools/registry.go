package tools

import (
	gatewaytools "github.com/BangRocket/mypalclara/go/internal/gateway/tools"
	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// ToolDef defines a tool for LLM binding.
type ToolDef struct {
	Schema  llm.ToolSchema
	Handler gatewaytools.Handler
}

// Registry holds all built-in tool definitions.
type Registry struct {
	tools map[string]ToolDef
}

// NewRegistry creates an empty tool registry.
func NewRegistry() *Registry {
	return &Registry{tools: make(map[string]ToolDef)}
}

// Register adds a tool definition to the registry.
func (r *Registry) Register(def ToolDef) {
	r.tools[def.Schema.Name] = def
}

// GetSchemas returns all tool schemas for LLM binding.
func (r *Registry) GetSchemas() []llm.ToolSchema {
	schemas := make([]llm.ToolSchema, 0, len(r.tools))
	for _, def := range r.tools {
		schemas = append(schemas, def.Schema)
	}
	return schemas
}

// RegisterAll registers all tool handlers with a gateway Executor.
func (r *Registry) RegisterAll(executor *gatewaytools.Executor) {
	for name, def := range r.tools {
		executor.Register(name, def.Handler)
	}
}
