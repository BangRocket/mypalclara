import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import type { GraphNode, GraphEdge } from "@/api/client";
import { EntityNode, TYPE_COLORS, type EntityNodeData } from "./EntityNode";

// ── d3-force layout ──────────────────────────────────────────────────────

interface SimNode extends SimulationNodeDatum {
  id: string;
}

function computeLayout(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
): { positions: Map<string, { x: number; y: number }>; connectionCounts: Map<string, number> } {
  if (graphNodes.length === 0) {
    return { positions: new Map(), connectionCounts: new Map() };
  }

  const connectionCounts = new Map<string, number>();
  for (const n of graphNodes) connectionCounts.set(n.id, 0);
  for (const e of graphEdges) {
    connectionCounts.set(e.source, (connectionCounts.get(e.source) || 0) + 1);
    connectionCounts.set(e.target, (connectionCounts.get(e.target) || 0) + 1);
  }

  const simNodes: SimNode[] = graphNodes.map((n) => ({ id: n.id }));
  const nodeIndex = new Map(simNodes.map((n, i) => [n.id, i]));

  const simLinks: SimulationLinkDatum<SimNode>[] = graphEdges
    .filter((e) => nodeIndex.has(e.source) && nodeIndex.has(e.target))
    .map((e) => ({ source: nodeIndex.get(e.source)!, target: nodeIndex.get(e.target)! }));

  const simulation = forceSimulation(simNodes)
    .force("link", forceLink(simLinks).distance(120).strength(0.4))
    .force("charge", forceManyBody().strength(-300))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(50))
    .stop();

  // Run simulation to convergence
  const iterations = Math.ceil(Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay()));
  for (let i = 0; i < iterations; i++) simulation.tick();

  const positions = new Map<string, { x: number; y: number }>();
  for (const sn of simNodes) {
    positions.set(sn.id, { x: sn.x ?? 0, y: sn.y ?? 0 });
  }

  return { positions, connectionCounts };
}

// ── Convert to React Flow ────────────────────────────────────────────────

function toReactFlowNodes(
  graphNodes: GraphNode[],
  positions: Map<string, { x: number; y: number }>,
  connectionCounts: Map<string, number>,
): Node<EntityNodeData>[] {
  return graphNodes.map((n) => {
    const pos = positions.get(n.id) || { x: 0, y: 0 };
    return {
      id: n.id,
      type: "entity",
      data: {
        label: n.name,
        entityType: n.type || "default",
        connectionCount: connectionCounts.get(n.id) || 0,
      },
      position: pos,
    };
  });
}

function toReactFlowEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    type: "smoothstep",
    animated: false,
    style: { strokeWidth: 1.5 },
    className: "!stroke-border",
    labelStyle: { fontSize: 10 },
    labelBgPadding: [6, 3] as [number, number],
    labelBgBorderRadius: 4,
    labelBgStyle: { opacity: 0.85 },
    labelClassName: "!fill-muted-foreground",
  }));
}

// ── Node types ───────────────────────────────────────────────────────────

const nodeTypes: NodeTypes = {
  entity: EntityNode,
};

// ── Component ────────────────────────────────────────────────────────────

interface GraphCanvasProps {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeClick?: (name: string) => void;
  onNodeDoubleClick?: (name: string) => void;
  selectedNode?: string | null;
}

export function GraphCanvas({
  graphNodes,
  graphEdges,
  onNodeClick,
  onNodeDoubleClick,
  selectedNode,
}: GraphCanvasProps) {
  const prevDataRef = useRef<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });

  const layout = useMemo(() => computeLayout(graphNodes, graphEdges), [graphNodes, graphEdges]);

  const initialNodes = useMemo(
    () => toReactFlowNodes(graphNodes, layout.positions, layout.connectionCounts),
    [graphNodes, layout],
  );
  const initialEdges = useMemo(() => toReactFlowEdges(graphEdges), [graphEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    // Only recalculate when data actually changes
    if (prevDataRef.current.nodes === graphNodes && prevDataRef.current.edges === graphEdges) return;
    prevDataRef.current = { nodes: graphNodes, edges: graphEdges };

    setNodes(toReactFlowNodes(graphNodes, layout.positions, layout.connectionCounts));
    setEdges(toReactFlowEdges(graphEdges));
  }, [graphNodes, graphEdges, layout, setNodes, setEdges]);

  // Update selection state
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        selected: n.data.label === selectedNode,
      })),
    );
  }, [selectedNode, setNodes]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.data.label as string);
    },
    [onNodeClick],
  );

  const handleNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeDoubleClick?.(node.data.label as string);
    },
    [onNodeDoubleClick],
  );

  return (
    <div className="w-full h-full bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: "smoothstep",
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} className="!bg-background" />
        <Controls className="!bg-card !border-border !rounded-lg !shadow-md [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground [&>button:hover]:!bg-muted" />
      </ReactFlow>
    </div>
  );
}

export { TYPE_COLORS };
