package gateway

import (
	"fmt"
	"sync"
	"time"

	"github.com/coder/websocket"
)

// ConnectedNode represents an adapter connected to the gateway.
type ConnectedNode struct {
	Info         NodeInfo
	Conn         *websocket.Conn
	RegisteredAt time.Time
	LastPing     time.Time
	Send         func(msg any) error
}

// NodeRegistry tracks connected adapter nodes.
type NodeRegistry struct {
	nodes map[string]*ConnectedNode
	mu    sync.RWMutex
}

// NewNodeRegistry creates a new empty NodeRegistry.
func NewNodeRegistry() *NodeRegistry {
	return &NodeRegistry{
		nodes: make(map[string]*ConnectedNode),
	}
}

// Register adds a node to the registry. Returns an error if the node ID is
// already registered.
func (r *NodeRegistry) Register(node *ConnectedNode) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.nodes[node.Info.NodeID]; exists {
		return fmt.Errorf("node %q already registered", node.Info.NodeID)
	}
	r.nodes[node.Info.NodeID] = node
	return nil
}

// Unregister removes a node from the registry by its ID.
func (r *NodeRegistry) Unregister(nodeID string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.nodes, nodeID)
}

// Get returns the ConnectedNode for the given ID, or nil if not found.
func (r *NodeRegistry) Get(nodeID string) *ConnectedNode {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.nodes[nodeID]
}

// GetByConnection returns the ConnectedNode associated with the given WebSocket
// connection, or nil if not found.
func (r *NodeRegistry) GetByConnection(conn *websocket.Conn) *ConnectedNode {
	r.mu.RLock()
	defer r.mu.RUnlock()
	for _, node := range r.nodes {
		if node.Conn == conn {
			return node
		}
	}
	return nil
}

// List returns a snapshot of all connected nodes.
func (r *NodeRegistry) List() []*ConnectedNode {
	r.mu.RLock()
	defer r.mu.RUnlock()
	result := make([]*ConnectedNode, 0, len(r.nodes))
	for _, node := range r.nodes {
		result = append(result, node)
	}
	return result
}

// Count returns the number of registered nodes.
func (r *NodeRegistry) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.nodes)
}

// UpdatePing updates the LastPing time for the given node.
func (r *NodeRegistry) UpdatePing(nodeID string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if node, ok := r.nodes[nodeID]; ok {
		node.LastPing = time.Now()
	}
}
